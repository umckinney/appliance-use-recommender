"""
EIA (U.S. Energy Information Administration) hourly generation data.

Fetches fuel-type generation for the BPA balancing authority (BPAT) and computes
carbon intensity using the same emission factors as bpa.py.

Strategy for future hours: EIA publishes only historical data. For hours that
haven't occurred yet, we use the same-hour-yesterday value as a proxy (daily
operational patterns on hydro-dominated grids are reasonably consistent).

Cache TTL: 30 minutes (EIA updates hourly).
Requires EIA_API_KEY — free key at https://api.eia.gov/
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from backend.integrations.bpa import EMISSION_FACTORS

EIA_BASE = "https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/"

EIA_FUEL_MAP: dict[str, str] = {
    "NG": "natural_gas",
    "WND": "wind",
    "WAT": "hydro",
    "NUC": "nuclear",
    "SUN": "wind",  # solar lifecycle ~20 g/kWh; wind (11) is closest available factor
    "COL": "coal",
    "OTH": "other",
}

CACHE_TTL_SECONDS = 3300  # 55 minutes — EIA updates hourly; polling faster wastes quota
_FALLBACK_CARBON = 200.0  # g/kWh — mid-range conservative default

_cache: dict[str, tuple[datetime, list[dict]]] = {}


async def get_carbon_forecast(
    api_key: str, hours: int = 48, ba_code: str = "BPAT"
) -> list[dict] | None:
    """
    Return hourly carbon intensity for the given balancing authority over the next `hours` slots.

    Uses same-time-yesterday for future hours (EIA has no day-ahead carbon forecast).
    Returns None if api_key is empty or the API call fails — caller should fall back
    to BPA flat-repeat.

    Returns:
        [{"hour_utc": str, "carbon_g_kwh": float}, ...] length == hours, or None
    """
    if not api_key:
        return None

    now = datetime.now(UTC)
    cache_key = f"eia_{ba_code}"
    cached = _cache.get(cache_key)
    if cached:
        cached_at, result = cached
        if (now - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return result

    try:
        start = now - timedelta(hours=49)
        raw = await _fetch_eia_raw(api_key, ba_code, start, now)
        rows = raw.get("response", {}).get("data", [])
        intensity_by_hour = _compute_intensity_by_hour(rows)
        result = _build_forecast(intensity_by_hour, now, hours)
    except Exception:
        return None

    _cache[cache_key] = (now, result)
    return result


async def _fetch_eia_raw(api_key: str, ba_code: str, start: datetime, end: datetime) -> dict:
    params = {
        "api_key": api_key,
        "frequency": "hourly",
        "data[]": "value",
        "facets[respondent][]": ba_code,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 350,  # 49 hours × 7 fuel types = 343 rows max
        "start": start.strftime("%Y-%m-%dT%H"),
        "end": end.strftime("%Y-%m-%dT%H"),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(EIA_BASE, params=params)
        resp.raise_for_status()
    return resp.json()


def _compute_intensity_by_hour(rows: list[dict]) -> dict[str, float]:
    """
    Aggregate EIA rows by hour and compute carbon_g_kwh via weighted average.

    EIA period format: "2026-04-17T14" (no minutes/seconds).
    Returns {period_str: carbon_g_kwh}.
    """
    by_hour: dict[str, dict[str, float]] = {}
    for row in rows:
        period = row.get("period", "")
        fuel = row.get("fueltype", "OTH")
        try:
            mw = max(0.0, float(row.get("value") or 0))
        except (TypeError, ValueError):
            mw = 0.0
        by_hour.setdefault(period, {})[fuel] = mw

    result: dict[str, float] = {}
    for period, fuels in by_hour.items():
        total_mw = sum(fuels.values())
        if total_mw == 0:
            result[period] = 0.0
            continue
        carbon = (
            sum(mw * EMISSION_FACTORS[EIA_FUEL_MAP.get(f, "other")] for f, mw in fuels.items())
            / total_mw
        )
        result[period] = round(carbon, 1)
    return result


def _build_forecast(
    intensity_by_hour: dict[str, float],
    now_utc: datetime,
    hours: int,
) -> list[dict]:
    """
    Build the forecast list using same-time-yesterday fallback for future hours.
    """
    now_floor = now_utc.replace(minute=0, second=0, microsecond=0)
    forecast = []
    for i in range(hours):
        target = now_floor + timedelta(hours=i)
        key = target.strftime("%Y-%m-%dT%H")
        if key in intensity_by_hour:
            carbon = intensity_by_hour[key]
        else:
            yesterday_key = (target - timedelta(hours=24)).strftime("%Y-%m-%dT%H")
            carbon = intensity_by_hour.get(yesterday_key, _FALLBACK_CARBON)
        forecast.append({"hour_utc": target.isoformat(), "carbon_g_kwh": carbon})
    return forecast
