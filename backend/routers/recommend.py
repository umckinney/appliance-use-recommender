"""GET /recommend/{appliance} — best time to run an appliance."""

import zoneinfo
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.engine import optimizer, rates, solar
from backend.integrations import bpa, eia, solar as solar_integration, solaredge
from backend.models import Appliance, User
from backend.schemas import RecommendResponse, RecommendWindow

router = APIRouter(prefix="/recommend", tags=["recommend"])


async def _get_user(api_key: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


@router.get("/{appliance_slug}", response_model=RecommendResponse)
async def recommend(
    appliance_slug: str,
    api_key: str,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(api_key, db)

    # Find the appliance
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

    # Fetch live data
    grid_data = await bpa.get_carbon_intensity()
    weather = await solar_integration.get_solar_forecast(user.lat, user.lon)
    solar_now = None
    if user.has_solar and (user.solaredge_site_id or user.solar_capacity_kw):
        solar_now = await solaredge.get_current_power(
            site_id=user.solaredge_site_id,
            api_key=user.solaredge_api_key,
        )

    # Build rate schedule (48h from now)
    tz = zoneinfo.ZoneInfo(user.timezone or "America/Los_Angeles")
    local_now = datetime.now(UTC).astimezone(tz)
    rate_schedule = rates.get_24h_schedule(user.utility_id, local_now)

    # Build carbon forecast — use EIA hourly data when available, fall back to BPA flat-repeat
    carbon_g_kwh = grid_data["carbon_g_kwh"]
    eia_forecast = None
    if settings.eia_api_key:
        eia_forecast = await eia.get_carbon_forecast(settings.eia_api_key, hours=len(rate_schedule))
    carbon_forecast = (
        eia_forecast
        if eia_forecast is not None
        else [{"carbon_g_kwh": carbon_g_kwh}] * len(rate_schedule)
    )

    # Build solar forecast (kW per hour)
    cfg = rates.load_utility(user.utility_id)
    nm_credit = cfg.get("net_metering_credit", 0.0)
    hourly = weather.get("hourly", [])

    solar_forecast_kw: list[float] = []
    for h in rate_schedule:
        # Match weather hour to schedule hour by index (both start at current hour)
        idx = len(solar_forecast_kw)
        irr = hourly[idx] if idx < len(hourly) else {}
        if user.has_solar:
            if solar_now and idx == 0:
                # First hour: use live SolarEdge reading if available
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

    # Score windows
    windows = optimizer.score_windows(
        rate_schedule=rate_schedule,
        carbon_forecast=carbon_forecast,
        solar_forecast=solar_forecast_kw,
        appliance_kwh=appliance.cycle_kwh,
        net_metering_credit_rate=nm_credit if user.net_metering else 0.0,
        optimization_weight=user.optimization_weight,
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

    # Find current hour window (first in rate_schedule order)
    current_window_raw = min(windows, key=lambda w: w.hour_local) if windows else None
    best = windows[0]

    data_sources = [
        "EIA hourly fuel-type data" if eia_forecast is not None else "BPA real-time grid"
    ]
    if solar_now:
        data_sources.append(f"SolarEdge ({solar_now['source']})")
    elif user.has_solar:
        data_sources.append("Open-Meteo solar irradiance estimate")
    data_sources.append("Open-Meteo weather forecast")

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
        data_sources=data_sources,
    )
