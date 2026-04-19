"""
SolarEdge integration — real-time solar generation.

Strategy (per plan):
1. Try the local inverter REST API first (http://<inverter_ip>/web/v1/status, port 80).
   No auth, no rate limits, LAN only. Only works on SetApp inverters with compatible firmware.
2. Fall back to SolarEdge Cloud Monitoring API (monitoring.solaredge.com).
   Requires site_id + api_key. Updates every 15 minutes — cache for 15 minutes.

If neither is configured, returns None (no solar data available).
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

CLOUD_API_BASE = "https://monitoringapi.solaredge.com"
CACHE_TTL_SECONDS = 900  # 15 minutes matches SolarEdge cloud update frequency

_cache: dict[str, tuple[datetime, dict | None]] = {}


async def get_current_power(
    site_id: str | None = None,
    api_key: str | None = None,
    local_ip: str | None = None,
) -> dict | None:
    """
    Return current solar generation in watts.

    Returns:
        {
            "power_w": float,         # current generation
            "energy_today_wh": float, # energy produced today so far
            "source": "local" | "cloud",
            "timestamp": str,
        }
        or None if not configured / unreachable.
    """
    cache_key = f"{site_id or ''}-{local_ip or ''}"
    now = datetime.now(UTC)

    if cache_key in _cache:
        cached_at, data = _cache[cache_key]
        if (now - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return data

    result = None

    # 1. Try local API
    if local_ip:
        result = await _get_local(local_ip)

    # 2. Fall back to cloud API
    if result is None and site_id and api_key:
        result = await _get_cloud(site_id, api_key)

    _cache[cache_key] = (now, result)
    return result


async def _get_local(ip: str) -> dict | None:
    """Query the SolarEdge inverter's local REST API."""
    url = f"http://{ip}/web/v1/status"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        # The local API returns protobuf-encoded data; community libraries decode it.
        # If we get JSON directly, try to parse common fields.
        power_w = float(data.get("powerWatt", data.get("power", 0)))
        return {
            "power_w": power_w,
            "energy_today_wh": float(data.get("energyToday", 0)),
            "source": "local",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception:
        return None


async def _get_cloud(site_id: str, api_key: str) -> dict | None:
    """Query the SolarEdge cloud monitoring API."""
    url = f"{CLOUD_API_BASE}/site/{site_id}/overview"
    params = {"api_key": api_key}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        overview = data.get("overview", {})
        current = overview.get("currentPower", {})
        day_data = overview.get("lastDayData", {})

        return {
            "power_w": float(current.get("power", 0)),
            "energy_today_wh": float(day_data.get("energy", 0)),
            "source": "cloud",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception:
        return None
