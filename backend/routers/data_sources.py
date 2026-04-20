"""GET /data-sources — data provenance for the authenticated user."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.deps import get_api_key
from backend.models import RateIngestionRun, User
from backend.schemas import DataSourceInfo, DataSourcesResponse

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


async def _get_user(api_key: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


async def _last_ingestion_at(db: AsyncSession, source_prefix: str) -> str | None:
    result = await db.execute(
        select(RateIngestionRun)
        .where(RateIngestionRun.source.startswith(source_prefix))
        .where(RateIngestionRun.status == "success")
        .order_by(RateIngestionRun.completed_at.desc())
    )
    run = result.scalars().first()
    if run and run.completed_at:
        return run.completed_at.isoformat()
    return None


@router.get("", response_model=DataSourcesResponse)
async def get_data_sources(
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(api_key, db)

    # Utility / rates tier
    uid = user.utility_id or ""
    if uid.startswith("eia_"):
        tier = user.utility_tier or 2
        rate_detail = (
            f"{user.utility_name or 'Unknown utility'} — "
            f"flat avg {user.utility_rate_avg:.4f} $/kWh"
            if user.utility_rate_avg
            else f"{user.utility_name or 'Unknown utility'} — flat average"
        )
        rate_freshness = await _last_ingestion_at(db, "openei_")
        utility_info = DataSourceInfo(
            source="OpenEI Zipcode CSV",
            tier=tier,
            detail=rate_detail,
            freshness=rate_freshness,
        )
        rates_info = DataSourceInfo(
            source="OpenEI Zipcode CSV (flat average)",
            tier=tier,
            detail=f"Source year: {user.utility_rate_avg and 2022}",
            freshness=rate_freshness,
        )
    else:
        utility_info = DataSourceInfo(
            source="FlowShift YAML rate file",
            tier=1,
            detail=uid,
            freshness=None,
        )
        rates_info = DataSourceInfo(
            source="FlowShift YAML TOU schedule",
            tier=1,
            detail=uid,
            freshness=None,
        )

    # Carbon
    if settings.eia_api_key:
        carbon_info = DataSourceInfo(
            source="EIA hourly fuel-type generation",
            detail="Hourly carbon intensity by balancing authority",
        )
    else:
        carbon_info = DataSourceInfo(
            source="BPA real-time grid",
            detail="Pacific Northwest hydro grid — flat repeat",
        )

    # Solar
    if user.has_solar:
        solar_info = DataSourceInfo(
            source="Open-Meteo NWP irradiance",
            detail="Cloud-adjusted direct + diffuse radiation forecast",
        )
    else:
        solar_info = DataSourceInfo(source="N/A", detail="Solar not configured")

    return DataSourcesResponse(
        utility=utility_info,
        carbon=carbon_info,
        solar=solar_info,
        rates=rates_info,
    )
