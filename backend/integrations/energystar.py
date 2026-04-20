"""ENERGY STAR Certified Products — bulk cache with change detection.

Covers dishwashers, clothes washers, and dryers only.

Per-cycle kWh derived from EIA RECS annual cycle counts:
  dishwasher: 215 cycles/year
  washer:     392 cycles/year
  dryer:      283 cycles/year  (also provides test_cycle_time_minutes directly)

Cache strategy:
- Full dataset per category is fetched once and held in memory for CACHE_TTL_SECONDS.
- On TTL expiry, the Socrata metadata endpoint is checked for rowsUpdatedAt. If the
  dataset hasn't changed since our last fetch, the TTL is reset without downloading data.
  Only an actual dataset update triggers a new bulk download.
- Net result: full download only on cold start + real ENERGY STAR DB updates (~monthly).
"""

from __future__ import annotations

import time
from typing import Any

import httpx

CACHE_TTL_SECONDS = 3600 * 12  # 12 hours between metadata checks

DATASETS: dict[str, tuple[str, int]] = {
    "dishwasher": ("q8py-6w3f", 215),
    "washer": ("bghd-e2wd", 392),
    "dryer": ("t9u7-4d2j", 283),
}

_BASE = "https://data.energystar.gov/resource"
_META_BASE = "https://data.energystar.gov/api/views"

# (fetched_at, rows_updated_at, normalized_records)
_FULL_CACHE: dict[str, tuple[float, str, list[dict]]] = {}


async def get_all_models(category: str) -> list[dict]:
    """Return all normalized models for a category, using bulk cache with change detection."""
    if category not in DATASETS:
        raise ValueError(f"Unsupported category {category!r}. Use: {list(DATASETS)}")

    dataset_id, annual_cycles = DATASETS[category]
    now = time.time()
    cached = _FULL_CACHE.get(category)

    if cached:
        fetched_at, cached_rows_updated_at, records = cached
        if now - fetched_at < CACHE_TTL_SECONDS:
            return records

        # TTL expired — check metadata before re-downloading
        try:
            rows_updated_at = await _fetch_rows_updated_at(dataset_id)
            if rows_updated_at == cached_rows_updated_at:
                # Dataset unchanged — reset TTL, keep records
                _FULL_CACHE[category] = (now, cached_rows_updated_at, records)
                return records
        except Exception:
            # Metadata check failed — reset TTL conservatively, serve stale
            _FULL_CACHE[category] = (now, cached_rows_updated_at, records)
            return records

    # Cold start or dataset changed — fetch full dataset
    rows_updated_at = ""
    try:
        rows_updated_at = await _fetch_rows_updated_at(dataset_id)
    except Exception:
        pass

    try:
        rows = await _fetch_all_raw(dataset_id)
    except Exception:
        rows = []

    records = _normalize(category, rows, annual_cycles)
    _FULL_CACHE[category] = (now, rows_updated_at, records)
    return records


async def get_brands(category: str) -> list[str]:
    """Return sorted list of unique brand names for a category."""
    records = await get_all_models(category)
    brands = sorted({r["brand"] for r in records if r["brand"]})
    return brands


async def get_models_for_brand(category: str, brand: str) -> list[dict]:
    """Return all models for a specific brand within a category."""
    records = await get_all_models(category)
    return [r for r in records if r["brand"].lower() == brand.lower()]


async def search_models(category: str, query: str, limit: int = 20) -> list[dict]:
    """Filter cached models by query string (brand or model match). Kept for compat."""
    records = await get_all_models(category)
    q = query.strip().lower()
    if not q:
        return records[:limit]
    matches = [
        r for r in records
        if q in r["brand"].lower() or q in r["model"].lower()
    ]
    return matches[:limit]


async def _fetch_rows_updated_at(dataset_id: str) -> str:
    """Fetch the rowsUpdatedAt timestamp from Socrata dataset metadata."""
    url = f"{_META_BASE}/{dataset_id}.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        meta = resp.json()
    return str(meta.get("rowsUpdatedAt", ""))


async def _fetch_all_raw(dataset_id: str) -> list[dict]:
    url = f"{_BASE}/{dataset_id}.json"
    params: dict[str, Any] = {"$limit": 10000}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _normalize(category: str, rows: list[dict], annual_cycles: int) -> list[dict]:
    results = []
    for row in rows:
        try:
            annual_kwh_str = (
                row.get("annual_energy_use_kwh_year")
                or row.get("estimated_annual_energy_use_kwh_yr")
                or row.get("estimated_annual_energy_use_kwh")
            )
            if annual_kwh_str is None:
                continue
            annual_kwh = float(annual_kwh_str)
            cycle_kwh = round(annual_kwh / annual_cycles, 3)

            cycle_minutes: int | None = None
            if category == "dryer":
                raw_min = (
                    row.get("estimated_energy_test_cycle_time_min")
                    or row.get("test_cycle_time_minutes")
                )
                if raw_min is not None:
                    cycle_minutes = int(float(raw_min))

            brand = (row.get("brand_name") or row.get("pd_id") or "").strip()
            model = (row.get("model_number") or row.get("model_name") or "").strip()
            if not brand and not model:
                continue

            # Wildcard prefix matching: strip suffix starting at "*"
            # e.g. "DLEX3900*" → prefix "DLEX3900", "WM3900H*A" → prefix "WM3900H"
            if "*" in model:
                model = model[: model.index("*")] + "*"

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
