"""GET /utilities/search?zip= — look up utilities by US ZIP code."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas import UtilitySearchResponse, UtilitySearchResult
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
