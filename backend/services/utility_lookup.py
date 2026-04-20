"""
Utility lookup service — wraps zipcode_rates integration with special-case handling.

Returns a list of UtilityMatch for the given ZIP. Handles:
- Texas retail choice (ERCOT): warn, return market-average placeholder
- California CCA zips: warn, return IOU match with note
- Multi-utility zips: return all matches (caller shows picker)
- No-data zips: return empty list (caller prompts manual entry)
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.zipcode_rates import UtilityMatch, lookup_by_zip

log = logging.getLogger(__name__)

# Texas ERCOT retail choice states/utilities produce unreliable rate data.
_TEXAS_WARNING = (
    "Texas has retail electricity choice — your actual rate may differ from the market average. "
    "You can enter your rate manually."
)

# California CCA (Community Choice Aggregation) adds complexity; IOU data is still usable.
_CA_CCA_WARNING = (
    "California Community Choice Aggregation (CCA) may mean your actual rate differs. "
    "The IOU rate shown is a typical baseline."
)


async def lookup_utilities_for_zip(
    zipcode: str, session: AsyncSession
) -> tuple[list[UtilityMatch], str | None]:
    """
    Look up utilities for a ZIP code.

    Returns (matches, warning_message | None).
    """
    matches = await lookup_by_zip(zipcode, session)

    if not matches:
        return [], None

    warning: str | None = None

    # Detect Texas retail choice: state TX + no/low IOU ownership
    texas_matches = [m for m in matches if m.state == "TX"]
    if texas_matches:
        non_iou = all(
            (m.ownership_type or "").lower() not in ("investor owned", "iou") for m in texas_matches
        )
        if non_iou or len(texas_matches) > 2:
            warning = _TEXAS_WARNING

    # Detect California CCA (multiple utilities, CA state)
    ca_matches = [m for m in matches if m.state == "CA"]
    if not warning and len(ca_matches) > 1:
        warning = _CA_CCA_WARNING

    return matches, warning
