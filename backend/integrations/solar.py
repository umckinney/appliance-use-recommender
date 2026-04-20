"""
Solar irradiance forecast via pvlib clear-sky model.

Uses pvlib's Ineichen clear-sky model — no external API, no license restrictions.
Trade-off: clear-sky doesn't account for cloud cover; estimates are optimistic on
overcast days but accurate enough for scheduling decisions.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pvlib

CACHE_TTL_SECONDS = 1800  # 30 minutes

_cache: dict[str, tuple[datetime, dict]] = {}


async def get_solar_forecast(lat: float, lon: float) -> dict:
    """
    Return 48-hour solar irradiance forecast using pvlib clear-sky model.

    Returns:
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
