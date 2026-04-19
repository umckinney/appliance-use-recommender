"""
BPA (Bonneville Power Administration) real-time grid data.

BPA is the balancing authority for Seattle City Light. Their public data endpoint
exposes real-time generation by fuel type (hydro, wind, thermal, nuclear, other).
We calculate carbon intensity from the fuel mix using standard emission factors.

No API key required. No commercial use restrictions.
Data updates approximately every 5 minutes.
Cache: 2 minutes (per plan).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx

# gCO2/kWh emission factors per fuel type (IPCC lifecycle medians)
EMISSION_FACTORS: dict[str, float] = {
    "hydro": 4,
    "wind": 11,
    "nuclear": 12,
    "natural_gas": 490,
    "coal": 820,
    "other": 300,  # conservative default for unknown sources
}

# BPA balancing authority table URL
BPA_TABLE_URL = "https://transmission.bpa.gov/business/operations/Wind/baltwg.txt"

_cache: dict[str, tuple[datetime, dict]] = {}
CACHE_TTL_SECONDS = 120


async def get_carbon_intensity() -> dict:
    """
    Return current carbon intensity and fuel mix for the BPA grid.

    Returns:
        {
            "carbon_g_kwh": float,
            "fuel_mix": {"hydro": MW, "wind": MW, "thermal": MW, ...},
            "total_mw": float,
            "timestamp": str,
            "source": "bpa"
        }
    """
    now = datetime.now(UTC)
    if "bpa" in _cache:
        cached_at, data = _cache["bpa"]
        if (now - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return data

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(BPA_TABLE_URL)
        resp.raise_for_status()

    data = _parse_bpa_table(resp.text)
    _cache["bpa"] = (now, data)
    return data


def _parse_bpa_table(text: str) -> dict:
    """
    Parse BPA's fixed-width text table to extract the most recent row.

    The file format is a fixed-width table where each row represents a 5-minute
    interval. Columns are: Date/Time, Load, Wind, Hydro, Fossil/Biomass, Nuclear, etc.
    """
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("Date")]

    # Find data lines (format: "MM/DD/YYYY HH:MM\t...")
    data_lines = [ln for ln in lines if re.match(r"\d{2}/\d{2}/\d{4}", ln.strip())]
    if not data_lines:
        raise ValueError("Could not parse BPA table — unexpected format")

    latest = data_lines[-1]
    parts = re.split(r"\t+", latest.strip())

    # BPA column order: DateTime, Load, Wind, Hydro, Fossil/Biomass, Nuclear
    def mw(val: str) -> float:
        try:
            return max(0.0, float(val.replace(",", "").strip()))
        except (ValueError, AttributeError):
            return 0.0

    wind = mw(parts[2]) if len(parts) > 2 else 0.0
    hydro = mw(parts[3]) if len(parts) > 3 else 0.0
    thermal = mw(parts[4]) if len(parts) > 4 else 0.0
    nuclear = mw(parts[5]) if len(parts) > 5 else 0.0

    total = wind + hydro + thermal + nuclear
    if total == 0:
        total = 1  # avoid division by zero

    carbon = (
        (wind * EMISSION_FACTORS["wind"])
        + (hydro * EMISSION_FACTORS["hydro"])
        + (thermal * EMISSION_FACTORS["natural_gas"])
        + (nuclear * EMISSION_FACTORS["nuclear"])
    ) / total

    return {
        "carbon_g_kwh": round(carbon, 1),
        "fuel_mix": {
            "wind_mw": wind,
            "hydro_mw": hydro,
            "thermal_mw": thermal,
            "nuclear_mw": nuclear,
        },
        "total_mw": round(total, 1),
        "timestamp": datetime.now(UTC).isoformat(),
        "source": "bpa",
    }
