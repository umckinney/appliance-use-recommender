"""
Open-Meteo integration — weather and solar irradiance forecast.

Free, no API key, global coverage, coordinate-based (address-level precision).
Used for: cloud cover, temperature, direct/diffuse solar irradiance.
Cache: 30 minutes (per plan).

Docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_SECONDS = 1800  # 30 minutes

_cache: dict[str, tuple[datetime, dict]] = {}


async def get_solar_forecast(lat: float, lon: float) -> dict:
    """
    Return 24-hour solar irradiance and cloud cover forecast for a location.

    Returns:
        {
            "hourly": [
                {
                    "time": "2026-03-29T10:00",
                    "direct_radiation_w_m2": float,
                    "diffuse_radiation_w_m2": float,
                    "cloud_cover_pct": float,
                    "temperature_c": float,
                },
                ...  # 24 entries
            ],
            "source": "open-meteo",
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

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "direct_radiation,diffuse_radiation,cloud_cover,temperature_2m",
        "forecast_days": 2,
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(FORECAST_URL, params=params)
        resp.raise_for_status()
        raw = resp.json()

    hourly = raw.get("hourly", {})
    times = hourly.get("time", [])
    direct = hourly.get("direct_radiation", [])
    diffuse = hourly.get("diffuse_radiation", [])
    cloud = hourly.get("cloud_cover", [])
    temp = hourly.get("temperature_2m", [])

    hours = [
        {
            "time": times[i],
            "direct_radiation_w_m2": direct[i] if i < len(direct) else 0.0,
            "diffuse_radiation_w_m2": diffuse[i] if i < len(diffuse) else 0.0,
            "cloud_cover_pct": cloud[i] if i < len(cloud) else 100.0,
            "temperature_c": temp[i] if i < len(temp) else 15.0,
        }
        for i in range(min(48, len(times)))  # 48 hours max
    ]

    result = {
        "hourly": hours,
        "source": "open-meteo",
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
