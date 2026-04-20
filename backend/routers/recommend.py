"""GET /recommend/{appliance} — best time to run an appliance."""

import zoneinfo
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.deps import get_api_key
from backend.engine import optimizer, rates, solar
from backend.engine.rates import get_ba_code
from backend.integrations import bpa, eia, solaredge
from backend.integrations import solar as solar_integration
from backend.limiter import _api_key_or_ip, limiter
from backend.models import Appliance, User
from backend.schemas import AllRecommendResponse, RecommendResponse, RecommendWindow

router = APIRouter(prefix="/recommend", tags=["recommend"])


async def _get_user(api_key: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


async def _fetch_shared_data(user: User) -> dict:
    """Fetch grid/weather/solar data shared across all appliance recommendations."""
    tz = zoneinfo.ZoneInfo(user.timezone or "America/Los_Angeles")
    local_now = datetime.now(UTC).astimezone(tz)
    rate_schedule = rates.get_24h_schedule(
        user.utility_id, local_now, flat_rate=user.utility_rate_avg
    )

    grid_data = await bpa.get_carbon_intensity()
    weather = await solar_integration.get_solar_forecast(user.lat, user.lon)
    solar_now = None
    if user.has_solar and (user.solaredge_site_id or user.solar_capacity_kw):
        solar_now = await solaredge.get_current_power(
            site_id=user.solaredge_site_id,
            api_key=user.solaredge_api_key,
        )

    carbon_g_kwh = grid_data["carbon_g_kwh"]
    ba_code = get_ba_code(user.utility_id) or "BPAT"
    eia_forecast = None
    if settings.eia_api_key:
        eia_forecast = await eia.get_carbon_forecast(
            settings.eia_api_key, hours=len(rate_schedule), ba_code=ba_code
        )
    carbon_forecast = (
        eia_forecast
        if eia_forecast is not None
        else [{"carbon_g_kwh": carbon_g_kwh}] * len(rate_schedule)
    )

    uid = user.utility_id or ""
    nm_credit = 0.0
    if not uid.startswith("eia_"):
        try:
            cfg = rates.load_utility(uid)
            nm_credit = cfg.get("net_metering_credit", 0.0)
        except ValueError:
            pass
    hourly = weather.get("hourly", [])

    solar_forecast_kw: list[float] = []
    for idx in range(len(rate_schedule)):
        irr = hourly[idx] if idx < len(hourly) else {}
        if user.has_solar:
            if solar_now and idx == 0:
                kw = solar_now["power_w"] / 1000.0
            elif user.solar_capacity_kw:
                kw = solar.estimate_power_from_irradiance(
                    direct_w_m2=irr.get("direct_radiation_w_m2", 0),
                    diffuse_w_m2=irr.get("diffuse_radiation_w_m2", 0),
                    capacity_kw=user.solar_capacity_kw,
                    tilt_deg=user.solar_tilt_deg or 20.0,
                    azimuth_deg=user.solar_azimuth_deg or 180.0,
                )
            else:
                kw = 0.0
        else:
            kw = 0.0
        solar_forecast_kw.append(kw)

    data_sources = [
        "EIA hourly fuel-type data" if eia_forecast is not None else "BPA real-time grid"
    ]
    if solar_now:
        data_sources.append(f"SolarEdge ({solar_now['source']})")
    elif user.has_solar:
        data_sources.append("Open-Meteo solar irradiance estimate")
    data_sources.append("Open-Meteo weather forecast")

    return {
        "rate_schedule": rate_schedule,
        "carbon_forecast": carbon_forecast,
        "solar_forecast_kw": solar_forecast_kw,
        "nm_credit": nm_credit if user.net_metering else 0.0,
        "data_sources": data_sources,
    }


def _build_recommend_response(
    appliance: "Appliance",
    shared: dict,
    optimization_weight: float,
) -> RecommendResponse:
    windows = optimizer.score_windows(
        rate_schedule=shared["rate_schedule"],
        carbon_forecast=shared["carbon_forecast"],
        solar_forecast=shared["solar_forecast_kw"],
        appliance_kwh=appliance.cycle_kwh,
        net_metering_credit_rate=shared["nm_credit"],
        optimization_weight=optimization_weight,
        cycle_minutes=appliance.cycle_minutes,
    )

    def to_schema(w: optimizer.Window) -> RecommendWindow:
        return RecommendWindow(
            hour_utc=w.hour_utc,
            hour_local=w.hour_local,
            rate_usd_kwh=w.rate_usd_kwh,
            carbon_g_kwh=w.carbon_g_kwh,
            solar_kw=w.solar_kw,
            net_cost_usd=w.net_cost_usd,
            carbon_kg=w.carbon_kg,
            score=w.score,
        )

    current_window_raw = min(windows, key=lambda w: w.hour_local) if windows else None
    best = windows[0]

    return RecommendResponse(
        appliance=appliance.name,
        text=optimizer.build_recommendation_text(
            appliance.name,
            best,
            current_window_raw or best,
            windows[:5],
        ),
        best_windows=[to_schema(w) for w in windows[:5]],
        current_window=to_schema(current_window_raw or best),
        cost_now_usd=(current_window_raw or best).net_cost_usd,
        cost_best_usd=best.net_cost_usd,
        carbon_now_kg=(current_window_raw or best).carbon_kg,
        carbon_best_kg=best.carbon_kg,
        data_sources=shared["data_sources"],
    )


@router.get("/all", response_model=AllRecommendResponse)
@limiter.limit("60/hour", key_func=_api_key_or_ip)
async def recommend_all(
    request: Request,
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(api_key, db)

    result = await db.execute(select(Appliance).where(Appliance.user_id == user.id))
    appliances = result.scalars().all()
    if not appliances:
        raise HTTPException(status_code=404, detail="No appliances configured.")

    shared = await _fetch_shared_data(user)
    per_appliance = [
        _build_recommend_response(a, shared, user.optimization_weight) for a in appliances
    ]

    # Best shared hour: hour_local with the lowest average score across all appliances
    hour_scores: dict[str, list[float]] = defaultdict(list)
    for rec in per_appliance:
        for w in rec.best_windows:
            hour_scores[w.hour_local].append(w.score)

    best_shared_start = min(hour_scores, key=lambda h: sum(hour_scores[h]) / len(hour_scores[h]))

    names = ", ".join(a.name for a in appliances)
    text = f"Best shared time to run {names} is {best_shared_start}."

    return AllRecommendResponse(
        text=text,
        best_shared_start=best_shared_start,
        per_appliance=per_appliance,
    )


@router.get("/{appliance_slug}", response_model=RecommendResponse)
@limiter.limit("60/hour", key_func=_api_key_or_ip)
async def recommend(
    request: Request,
    appliance_slug: str,
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(api_key, db)

    result = await db.execute(
        select(Appliance).where(Appliance.user_id == user.id, Appliance.slug == appliance_slug)
    )
    appliance = result.scalar_one_or_none()
    if not appliance:
        raise HTTPException(
            status_code=404,
            detail=f"Appliance {appliance_slug!r} not found. "
            f"Add it via POST /appliances or during onboarding.",
        )

    shared = await _fetch_shared_data(user)
    return _build_recommend_response(appliance, shared, user.optimization_weight)
