"""
Geocoding via Nominatim (OpenStreetMap).

Free, no API key required, open data (ODbL license — permissive for commercial use).
Usage policy: include User-Agent header, max 1 req/sec, no bulk geocoding.
Geocoding only occurs at onboarding — well within policy.
"""

from __future__ import annotations

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "FlowShift/1.0 (contact@flowshift.app)"


async def geocode(address: str) -> dict | None:
    """
    Geocode a street address to lat/lon.
    Returns {"lat": float, "lon": float, "display_name": str} or None.
    """
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        results = resp.json()

    if not results:
        return None

    r = results[0]
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "display_name": r.get("display_name", address),
    }
