"""Utility lookup endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.integrations.urdb import get_net_metering_credit, summarise_periods
from backend.models import UrdbRate, UtilityRecord
from backend.schemas import (
    TariffListResponse,
    UrdbTariff,
    UtilitySearchResponse,
    UtilitySearchResult,
)
from backend.services.utility_lookup import lookup_utilities_for_zip

router = APIRouter(prefix="/utilities", tags=["utilities"])


@router.get("/search", response_model=UtilitySearchResponse)
async def search_utilities(
    zip: str = Query(..., min_length=3, max_length=10, description="US ZIP code"),
    db: AsyncSession = Depends(get_db),
):
    matches, warning = await lookup_utilities_for_zip(zip, db)
    return UtilitySearchResponse(
        zipcode=zip.strip().zfill(5),
        utilities=[
            UtilitySearchResult(
                eia_id=m.eia_id,
                utility_name=m.utility_name,
                state=m.state,
                ownership_type=m.ownership_type,
                residential_rate_avg=m.residential_rate_avg,
                source_year=m.source_year,
                is_primary=m.is_primary,
                utility_id=m.utility_id,
            )
            for m in matches
        ],
        warning=warning,
    )


@router.get("/tariffs", response_model=TariffListResponse)
async def list_tariffs(
    eia_id: int = Query(..., description="EIA utility ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all active URDB residential tariffs for a given EIA utility.

    Returns an empty tariffs list when no URDB data is available for this
    utility — the caller should fall back to the Tier 2 flat-rate path.
    """
    utility_result = await db.execute(select(UtilityRecord).where(UtilityRecord.eia_id == eia_id))
    utility = utility_result.scalar_one_or_none()

    tariff_result = await db.execute(
        select(UrdbRate).where(
            UrdbRate.eia_id == eia_id,
            UrdbRate.is_active == True,  # noqa: E712
        )
    )
    records = tariff_result.scalars().all()

    tariffs = []
    for r in records:
        raw = r.raw_json or {}
        tariffs.append(
            UrdbTariff(
                urdb_label=r.urdb_label,
                name=r.name,
                utility_id=f"urdb_{r.urdb_label}",
                effective_date=r.effective_date,
                is_active=r.is_active,
                periods=summarise_periods(raw),
                net_metering_credit=get_net_metering_credit(raw),
            )
        )

    return TariffListResponse(
        eia_id=eia_id,
        utility_name=utility.name if utility else None,
        tariffs=tariffs,
    )
