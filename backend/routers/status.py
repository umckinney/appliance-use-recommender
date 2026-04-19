"""GET /status — current grid and solar snapshot for the authenticated user."""

import zoneinfo
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.engine import optimizer, rates
from backend.integrations import bpa, solaredge
from backend.models import User
from backend.schemas import StatusResponse

router = APIRouter(prefix="/status", tags=["status"])


async def _get_user(api_key: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


@router.get("", response_model=StatusResponse)
async def status(api_key: str, db: AsyncSession = Depends(get_db)):
    user = await _get_user(api_key, db)

    grid_data = await bpa.get_carbon_intensity()

    solar_kw = None
    if user.has_solar and (user.solaredge_site_id or user.solar_capacity_kw):
        solar_now = await solaredge.get_current_power(
            site_id=user.solaredge_site_id,
            api_key=user.solaredge_api_key,
        )
        if solar_now:
            solar_kw = solar_now["power_w"] / 1000.0

    tz = zoneinfo.ZoneInfo(user.timezone or "America/Los_Angeles")
    local_now = datetime.now(UTC).astimezone(tz)
    rate, period = rates.get_rate(user.utility_id, local_now)

    carbon_g_kwh = grid_data["carbon_g_kwh"]

    return StatusResponse(
        grid_zone=grid_data.get("zone", "BPA"),
        carbon_intensity_g_kwh=carbon_g_kwh,
        carbon_label=optimizer.carbon_label(carbon_g_kwh),
        current_rate_usd_kwh=rate,
        rate_period=period,
        solar_kw=solar_kw,
        timestamp=local_now.isoformat(),
    )
