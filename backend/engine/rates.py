"""
Utility rate loader and TOU schedule resolver.

Reads YAML rate files from backend/data/utility_rates/ and computes
the applicable rate and period for any local datetime.

Three utility tiers are supported:
  Tier 1 YAML   utility_id is a slug like 'seattle_city_light'
  Tier 1 URDB   utility_id starts with 'urdb_'; caller passes urdb_raw
  Tier 2 flat   utility_id starts with 'eia_'; caller passes flat_rate
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

RATES_DIR = Path(__file__).parent.parent / "data" / "utility_rates"

_rate_cache: dict[str, dict] = {}


def load_utility(utility_id: str) -> dict:
    """Load and cache a utility rate config by ID."""
    if utility_id not in _rate_cache:
        path = RATES_DIR / f"{utility_id}.yaml"
        if not path.exists():
            raise ValueError(f"Unknown utility: {utility_id!r}. Add a YAML to {RATES_DIR}")
        with open(path) as f:
            _rate_cache[utility_id] = yaml.safe_load(f)
    return _rate_cache[utility_id]


def get_ba_code(utility_id: str) -> str | None:
    """Return the EIA balancing authority code for a utility, or None if not mapped."""
    try:
        cfg = load_utility(utility_id)
    except ValueError:
        return None
    return cfg.get("balancing_authority") or None


def list_utilities() -> list[dict]:
    """Return a list of all supported utilities (id + name)."""
    results = []
    for path in sorted(RATES_DIR.glob("*.yaml")):
        if path.name == "TEMPLATE.yaml":
            continue
        with open(path) as f:
            cfg = yaml.safe_load(f)
        results.append({"utility_id": cfg["utility_id"], "utility_name": cfg["utility_name"]})
    return results


def get_rate(
    utility_id: str,
    local_dt: datetime,
    flat_rate: float | None = None,
    urdb_raw: dict | None = None,
) -> tuple[float, str]:
    """
    Return (rate_usd_kwh, period_name) for a local datetime.

    Period name is one of: 'off_peak', 'mid_peak', 'peak'.
    """
    if utility_id and utility_id.startswith("eia_"):
        rate = flat_rate if flat_rate is not None else 0.12  # 12¢/kWh fallback
        return rate, "off_peak"

    if utility_id and utility_id.startswith("urdb_"):
        from backend.integrations.urdb import get_rate_from_raw

        return get_rate_from_raw(urdb_raw or {}, local_dt)

    cfg = load_utility(utility_id)
    schedules = cfg["schedules"]
    rates = cfg["rates"]
    holidays = set(cfg.get("holidays", []))

    # Determine day type
    mmdd = local_dt.strftime("%m-%d")
    weekday = local_dt.weekday()  # 0=Mon, 6=Sun
    is_weekend = weekday == 6 or mmdd in holidays  # Sunday only; Saturday is weekday/peak
    schedule_key = "weekend" if is_weekend else "weekday"

    schedule = schedules.get(schedule_key, schedules.get("weekday", []))
    hour = local_dt.hour

    for block in schedule:
        if block["start_hour"] <= hour < block["end_hour"]:
            period = block["period"]
            return rates[period], period

    # Fallback: last block of the day
    last = schedule[-1]
    period = last["period"]
    return rates[period], period


def get_24h_schedule(
    utility_id: str,
    local_dt: datetime,
    flat_rate: float | None = None,
    urdb_raw: dict | None = None,
) -> list[dict]:
    """
    Return a 48-element list of hourly rate/period data starting at midnight of local_dt's day.

    Pass flat_rate for Tier 2 (eia_*) utilities, urdb_raw for Tier 1 URDB utilities.
    """
    from datetime import timedelta

    base = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    results = []
    for h in range(48):  # 48h forecast
        hour_dt = base + timedelta(hours=h)
        rate, period = get_rate(utility_id, hour_dt, flat_rate=flat_rate, urdb_raw=urdb_raw)
        results.append(
            {
                "hour_local": hour_dt.isoformat(),
                "rate_usd_kwh": rate,
                "rate_period": period,
            }
        )
    return results
