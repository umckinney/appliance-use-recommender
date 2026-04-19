"""
Solar irradiance forecast via pvlib clear-sky model.

Uses pvlib's Ineichen clear-sky model — no external API, no license restrictions.
Trade-off: clear-sky doesn't account for cloud cover; estimates are optimistic on
overcast days but accurate enough for scheduling decisions.

Geocoding via Nominatim (OpenStreetMap) — free, open data (ODbL), no API key.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pandas as pd
import pvlib

CACHE_TTL_SECONDS = 1800  # 30 minutes

_cache: dict[str, tuple[datetime, dict]] = {}


async def get_solar_forecast(lat: float, lon: float) -> dict:
    """
    Return 48-hour solar irradiance forecast using pvlib clear-sky model.

    Returns the same shape as the previous Open-Meteo implementation so callers
    need no changes:
        {
            "hourly": [
                {
                    "time": str (ISO8601),
                    "direct_radiation_w_m2": float,   # DNI W/m²
                    "diffuse_radiation_w_m2": float,  # DHI W/m²
                    "cloud_cover_pct": float,          # always 0.0 (clear-sky)
                    "temperature_c": float,            # always 15.0 (no weather data)
                },
                ...  # 48 entries
            ],
            "source": "pvlib-clearsky",
            "lat": float,
            "lon": float,
        }
    """
    cache_key = f"{lat:.3f},{lon:.3f}"
    now = datetime.now(UTC)

    if cache_key in _cache:
        cached_at, data = _cache[cache_key]
        if (now - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return data

    start = now.replace(minute=0, second=0, microsecond=0)
    times = pd.date_range(start=start, periods=48, freq="h", tz="UTC")

    location = pvlib.location.Location(latitude=lat, longitude=lon, tz="UTC")
    clearsky = location.get_clearsky(times)  # columns: ghi, dni, dhi

    hours = [
        {
            "time": t.isoformat(),
            "direct_radiation_w_m2": float(clearsky["dni"].iloc[i]),
            "diffuse_radiation_w_m2": float(clearsky["dhi"].iloc[i]),
            "cloud_cover_pct": 0.0,
            "temperature_c": 15.0,
        }
        for i, t in enumerate(times)
    ]

    result = {
        "hourly": hours,
        "source": "pvlib-clearsky",
        "lat": lat,
        "lon": lon,
        "fetched_at": now.isoformat(),
    }
    _cache[cache_key] = (now, result)
    return result


async def geocode(address: str) -> dict | None:
    """
    Geocode a street address to lat/lon using Nominatim (OpenStreetMap).
    Returns {"lat": float, "lon": float, "display_name": str} or None.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "FlowShift/0.1 (contact@flowshift.app)"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers=headers)
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
