"""
Geocoding via Nominatim (OpenStreetMap).

Free, no API key required, open data (ODbL license — permissive for commercial use).
Usage policy: include User-Agent header, max 1 req/sec, no bulk geocoding.
Geocoding only occurs at onboarding — well within policy.

Fallback strategy when Nominatim is unavailable:
  1. Extract ZIP/postal code from the address string via regex
  2. Query zip_centroid table (populated by scripts/ingest_zipcode_rates.py)
  3. Store result with precise=False; surface a user-visible warning
"""

from __future__ import annotations

import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "FlowShift/1.0 (contact@flowshift.app)"

# Matches 5-digit US ZIP optionally followed by -NNNN, after whitespace/comma
_US_ZIP_RE = re.compile(r"(?:^|[\s,])(\d{5})(?:-\d{4})?(?:\s|,|$)")


def extract_zip(address: str) -> str | None:
    """Extract the last US 5-digit ZIP from an address string, or None."""
    matches = _US_ZIP_RE.findall(address)
    return matches[-1] if matches else None


async def _zip_centroid_from_db(zipcode: str, session: AsyncSession) -> tuple[float, float] | None:
    from backend.models import ZipCentroid

    result = await session.execute(
        select(ZipCentroid).where(ZipCentroid.zipcode == zipcode.strip().zfill(5))
    )
    row = result.scalar_one_or_none()
    return (row.lat, row.lng) if row else None


async def geocode(address: str) -> dict | None:
    """
    Geocode a street address to lat/lon via Nominatim.

    Returns {"lat", "lon", "display_name", "country_code", "postcode", "precise": True}
    or None on timeout / no results.
    """
    params = {"q": address, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            results = resp.json()
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
        return None

    if not results:
        return None

    r = results[0]
    addr_detail = r.get("address", {})
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "display_name": r.get("display_name", address),
        "country_code": addr_detail.get("country_code", "").lower(),
        "postcode": addr_detail.get("postcode", ""),
        "precise": True,
    }


async def geocode_with_fallback(
    address: str, postal_code: str = "", session: AsyncSession | None = None
) -> dict:
    """
    Geocode with DB ZIP centroid fallback.

    Always returns a result. Check result["precise"] to know whether Nominatim
    succeeded (True) or a ZIP centroid was used (False).

    Requires a DB session to perform the centroid lookup. If session is None,
    centroid fallback is skipped and lat/lon will be None on Nominatim failure.
    """
    geo = await geocode(address)
    if geo:
        return geo

    # Fallback: use explicit postal_code first, then extract from address string
    zip_candidate = postal_code.strip() or extract_zip(address) or ""

    if zip_candidate and session is not None:
        centroid = await _zip_centroid_from_db(zip_candidate, session)
        if centroid:
            return {
                "lat": centroid[0],
                "lon": centroid[1],
                "display_name": address,
                "country_code": "us",
                "postcode": zip_candidate.zfill(5),
                "precise": False,
                "fallback_reason": (
                    "Address lookup is temporarily unavailable. "
                    "Using your ZIP code's center point — solar estimates may be "
                    "slightly less precise. This resolves automatically."
                ),
            }

    return {
        "lat": None,
        "lon": None,
        "display_name": address,
        "country_code": "",
        "postcode": zip_candidate,
        "precise": False,
        "fallback_reason": (
            "Could not determine your location. " "Please check your address or ZIP code."
        ),
    }
