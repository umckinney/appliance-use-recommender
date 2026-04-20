"""
Solar irradiance forecast.

Primary: Open-Meteo hourly solar radiation — cloud-adjusted NWP forecast, no API key.
Fallback: pvlib Ineichen clear-sky model (used when Open-Meteo is unreachable).

Open-Meteo updates every hour and reflects actual cloud cover, making estimates
honest on overcast days (pvlib was systematically optimistic by 3-5x on cloudy days).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
import pandas as pd
import pvlib

_log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 1800  # 30 minutes

_cache: dict[str, tuple[datetime, dict]] = {}

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def _open_meteo_forecast(lat: float, lon: float) -> list[dict]:
    """Fetch 48h cloud-adjusted irradiance from Open-Meteo. Raises on failure."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "direct_radiation,diffuse_radiation",
        "timezone": "UTC",
        "forecast_days": 2,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    times = data["hourly"]["time"]
    direct = data["hourly"]["direct_radiation"]
    diffuse = data["hourly"]["diffuse_radiation"]

    return [
        {
            "time": times[i],
            "direct_radiation_w_m2": float(direct[i] or 0),
            "diffuse_radiation_w_m2": float(diffuse[i] or 0),
            "cloud_cover_pct": None,  # Open-Meteo doesn't return this separately
            "temperature_c": 15.0,
        }
        for i in range(min(48, len(times)))
    ]


def _pvlib_fallback(lat: float, lon: float) -> list[dict]:
    """Clear-sky fallback via pvlib Ineichen model (no external call)."""
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    times = pd.date_range(start=now, periods=48, freq="h", tz="UTC")
    location = pvlib.location.Location(latitude=lat, longitude=lon, tz="UTC")
    clearsky = location.get_clearsky(times)

    return [
        {
            "time": t.isoformat(),
            "direct_radiation_w_m2": float(clearsky["dni"].iloc[i]),
            "diffuse_radiation_w_m2": float(clearsky["dhi"].iloc[i]),
            "cloud_cover_pct": 0.0,
            "temperature_c": 15.0,
        }
        for i, t in enumerate(times)
    ]


async def get_solar_forecast(lat: float, lon: float) -> dict:
    """
    Return 48-hour solar irradiance forecast.

    Tries Open-Meteo first (cloud-adjusted). Falls back to pvlib clear-sky on error.

    Returns:
        {
            "hourly": [
                {
                    "time": str (ISO8601),
                    "direct_radiation_w_m2": float,
                    "diffuse_radiation_w_m2": float,
                    "cloud_cover_pct": float | None,
                    "temperature_c": float,
                },
                ...  # 48 entries
            ],
            "source": "open-meteo" | "pvlib-clearsky-fallback",
            "lat": float,
            "lon": float,
            "fetched_at": str,
        }
    """
    cache_key = f"{lat:.3f},{lon:.3f}"
    now = datetime.now(UTC)

    if cache_key in _cache:
        cached_at, data = _cache[cache_key]
        if (now - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return data

    source = "open-meteo"
    try:
        hours = await _open_meteo_forecast(lat, lon)
    except Exception as exc:
        _log.warning("Open-Meteo solar fetch failed (%s), falling back to pvlib", exc)
        hours = _pvlib_fallback(lat, lon)
        source = "pvlib-clearsky-fallback"

    result = {
        "hourly": hours,
        "source": source,
        "lat": lat,
        "lon": lon,
        "fetched_at": now.isoformat(),
    }
    _cache[cache_key] = (now, result)
    return result
