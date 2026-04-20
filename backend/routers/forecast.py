"""GET /forecast — 24h carbon + rate + solar outlook for the authenticated user."""

import zoneinfo
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.deps import get_api_key
from backend.engine import rates, solar
from backend.engine.rates import get_ba_code
from backend.integrations import bpa, eia, solaredge
from backend.integrations import solar as solar_integration
from backend.models import User
from backend.schemas import ForecastHour, ForecastResponse

router = APIRouter(prefix="/forecast", tags=["forecast"])


async def _get_user(api_key: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


@router.get("", response_model=ForecastResponse)
async def forecast(api_key: str = Depends(get_api_key), db: AsyncSession = Depends(get_db)):
    user = await _get_user(api_key, db)

    tz = zoneinfo.ZoneInfo(user.timezone or "America/Los_Angeles")
    local_now = datetime.now(UTC).astimezone(tz)

    # Fetch live data
    grid_data = await bpa.get_carbon_intensity()
    weather = await solar_integration.get_solar_forecast(user.lat, user.lon)
    bpa_carbon_g_kwh = grid_data["carbon_g_kwh"]

    solar_now = None
    if user.has_solar and (user.solaredge_site_id or user.solar_capacity_kw):
        solar_now = await solaredge.get_current_power(
            site_id=user.solaredge_site_id,
            api_key=user.solaredge_api_key,
        )

    rate_schedule = rates.get_24h_schedule(
        user.utility_id, local_now, flat_rate=user.utility_rate_avg
    )

    ba_code = get_ba_code(user.utility_id) or "BPAT"
    eia_forecast = None
    if settings.eia_api_key:
        eia_forecast = await eia.get_carbon_forecast(
            settings.eia_api_key, hours=len(rate_schedule), ba_code=ba_code
        )
    hourly = weather.get("hourly", [])

    hours: list[ForecastHour] = []
    for idx, h in enumerate(rate_schedule[:24]):
        irr = hourly[idx] if idx < len(hourly) else {}

        solar_kw: float | None = None
        if user.has_solar:
            if solar_now and idx == 0:
                solar_kw = solar_now["power_w"] / 1000.0
            elif user.solar_capacity_kw:
                solar_kw = solar.estimate_power_from_irradiance(
                    direct_w_m2=irr.get("direct_radiation_w_m2", 0),
                    diffuse_w_m2=irr.get("diffuse_radiation_w_m2", 0),
                    capacity_kw=user.solar_capacity_kw,
                    tilt_deg=user.solar_tilt_deg or 20.0,
                    azimuth_deg=user.solar_azimuth_deg or 180.0,
                )
            else:
                solar_kw = 0.0

        hours.append(
            ForecastHour(
                hour_local=h["hour_local"],
                carbon_g_kwh=(
                    eia_forecast[idx]["carbon_g_kwh"] if eia_forecast else bpa_carbon_g_kwh
                ),
                rate_usd_kwh=h["rate_usd_kwh"],
                rate_period=h["rate_period"],
                solar_kw=solar_kw,
            )
        )

    # Best window = lowest combined score (cheapest + cleanest)
    # For the forecast, just find the off-peak window with lowest rate
    best_start = min(hours, key=lambda x: x.rate_usd_kwh).hour_local

    return ForecastResponse(
        hours=hours,
        best_window_start=best_start,
        utility_id=user.utility_id,
    )
