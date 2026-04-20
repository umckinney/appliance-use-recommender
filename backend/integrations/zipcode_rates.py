"""
ZIP code → utility lookup backed by the zipcode_utility + utility DB tables.

Call lookup_by_zip(zip, session) to get all matching utilities for a ZIP.
Results include residential rate average, tier, and whether the utility is
the primary (most common) one for that ZIP.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import UtilityRecord, ZipcodeUtility


@dataclass
class UtilityMatch:
    eia_id: int
    utility_name: str
    state: str | None
    ownership_type: str | None
    residential_rate_avg: float | None  # $/kWh
    source_year: int | None
    is_primary: bool
    utility_id: str  # "eia_{eia_id}" — usable as User.utility_id for Tier 2


async def lookup_by_zip(zipcode: str, session: AsyncSession) -> list[UtilityMatch]:
    """
    Return all utilities serving the given ZIP code, primary first.

    Returns an empty list if the ZIP has no data (caller should prompt manual entry).
    """
    normalized = zipcode.strip().zfill(5)

    result = await session.execute(
        select(ZipcodeUtility, UtilityRecord)
        .join(UtilityRecord, ZipcodeUtility.eia_id == UtilityRecord.eia_id)
        .where(ZipcodeUtility.zipcode == normalized)
        .order_by(ZipcodeUtility.is_primary.desc(), UtilityRecord.name)
    )
    rows = result.all()

    matches = []
    for zcu, util in rows:
        matches.append(
            UtilityMatch(
                eia_id=util.eia_id,
                utility_name=util.name,
                state=util.state,
                ownership_type=util.ownership_type,
                residential_rate_avg=zcu.residential_rate_avg,
                source_year=zcu.source_year,
                is_primary=zcu.is_primary,
                utility_id=f"eia_{util.eia_id}",
            )
        )
    return matches
