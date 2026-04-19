"""ENERGY STAR Certified Products API client.

Covers dishwashers, clothes washers, and dryers only.
Pool pumps, HVAC, and EV chargers remain as manual entry.

Per-cycle kWh derived from EIA RECS annual cycle counts:
  dishwasher: 215 cycles/year
  washer:     392 cycles/year
  dryer:      283 cycles/year  (also provides test_cycle_time_minutes directly)
"""

from __future__ import annotations

import time
from typing import Any

import httpx

_CACHE: dict[str, tuple[float, list[dict]]] = {}
CACHE_TTL_SECONDS = 3600 * 12  # ENERGY STAR data updates monthly at most

DATASETS: dict[str, tuple[str, int]] = {
    "dishwasher": ("q8py-6w3f", 215),
    "washer": ("bghd-e2wd", 392),
    "dryer": ("t9u7-4d2j", 283),
}

_BASE = "https://data.energystar.gov/resource"


async def search_models(category: str, query: str, limit: int = 20) -> list[dict]:
    """Search ENERGY STAR certified products for a given category and query string.

    Returns normalized list:
      [{"brand": str, "model": str, "cycle_kwh": float, "cycle_minutes": int | None}]
    cycle_minutes is populated for dryers (from test_cycle_time), None for others.
    """
    if category not in DATASETS:
        raise ValueError(f"Unsupported category {category!r}. Use: {list(DATASETS)}")

    cache_key = f"{category}:{query}:{limit}"
    cached = _CACHE.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    dataset_id, annual_cycles = DATASETS[category]
    try:
        rows = await _fetch_raw(dataset_id, query, limit)
    except Exception:
        return []

    results = _normalize(category, rows, annual_cycles)
    _CACHE[cache_key] = (time.time(), results)
    return results


async def _fetch_raw(dataset_id: str, query: str, limit: int) -> list[dict]:
    url = f"{_BASE}/{dataset_id}.json"
    params: dict[str, Any] = {"$limit": limit}
    if query:
        params["$q"] = query
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _normalize(category: str, rows: list[dict], annual_cycles: int) -> list[dict]:
    results = []
    for row in rows:
        try:
            # Field names vary by dataset (confirmed against live Socrata responses)
            annual_kwh_str = (
                row.get("annual_energy_use_kwh_year")          # dishwasher + washer
                or row.get("estimated_annual_energy_use_kwh_yr")  # dryer
                or row.get("estimated_annual_energy_use_kwh")  # legacy fallback
            )
            if annual_kwh_str is None:
                continue
            annual_kwh = float(annual_kwh_str)
            cycle_kwh = round(annual_kwh / annual_cycles, 3)

            cycle_minutes: int | None = None
            if category == "dryer":
                raw_min = (
                    row.get("estimated_energy_test_cycle_time_min")  # actual field name
                    or row.get("test_cycle_time_minutes")            # legacy fallback
                )
                if raw_min is not None:
                    cycle_minutes = int(float(raw_min))

            brand = (row.get("brand_name") or row.get("pd_id") or "").strip()
            model = (row.get("model_number") or row.get("model_name") or "").strip()
            if not brand and not model:
                continue

            results.append(
                {
                    "brand": brand,
                    "model": model,
                    "cycle_kwh": cycle_kwh,
                    "cycle_minutes": cycle_minutes,
                }
            )
        except (ValueError, TypeError):
            continue
    return results
