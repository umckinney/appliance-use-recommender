"""
URDB rate parser — converts a URDB rate record's raw JSON into FlowShift's
TOU format (rate_usd_kwh, period_name) for any local datetime.

URDB schema reference: https://openei.org/services/doc/rest/util_rates/
Key fields used:
  energyratestructure    list[list[{rate, adj, sell, unit}]]  per-period tiers
  energyweekdayschedule  list[list[int]]  12 months × 24 hours of period indices
  energyweekendschedule  same for weekends
  flatdemandstructure    IGNORED (demand charges not supported)
"""

from __future__ import annotations

from datetime import datetime

# Period name thresholds: by sorted-rate rank
_PERIOD_NAMES = {1: ["off_peak"], 2: ["off_peak", "peak"]}

_FALLBACK_RATE = (0.12, "off_peak")


def _build_period_map(raw_json: dict) -> dict[int, tuple[float, str]]:
    """Return {period_idx: (rate_usd_kwh, period_name)} from energyratestructure."""
    structure = raw_json.get("energyratestructure") or []
    period_rates: dict[int, float] = {}
    for idx, tiers in enumerate(structure):
        if not tiers:
            continue
        tier = tiers[0]
        rate = (tier.get("rate") or 0.0) + (tier.get("adj") or 0.0)
        period_rates[idx] = rate

    if not period_rates:
        return {0: _FALLBACK_RATE}

    sorted_items = sorted(period_rates.items(), key=lambda x: x[1])
    n = len(sorted_items)
    period_map: dict[int, tuple[float, str]] = {}
    for rank, (idx, rate) in enumerate(sorted_items):
        if n == 1:
            name = "off_peak"
        elif n == 2:
            name = "off_peak" if rank == 0 else "peak"
        else:
            if rank == 0:
                name = "off_peak"
            elif rank == n - 1:
                name = "peak"
            else:
                name = "mid_peak"
        period_map[idx] = (rate, name)
    return period_map


def _lookup_period(raw_json: dict, local_dt: datetime) -> int:
    """Return the URDB period index for a given local datetime."""
    is_weekend = local_dt.weekday() == 6
    schedule_key = "energyweekendschedule" if is_weekend else "energyweekdayschedule"
    schedule = raw_json.get(schedule_key) or raw_json.get("energyweekdayschedule") or []

    month_idx = local_dt.month - 1
    hour_idx = local_dt.hour

    if not schedule or month_idx >= len(schedule):
        return 0

    month_row = schedule[month_idx]
    if not month_row:
        return 0

    hour_idx = min(hour_idx, len(month_row) - 1)
    return int(month_row[hour_idx])


def get_rate_from_raw(raw_json: dict, local_dt: datetime) -> tuple[float, str]:
    """Return (rate_usd_kwh, period_name) for a local datetime from URDB raw JSON."""
    if not raw_json:
        return _FALLBACK_RATE
    period_map = _build_period_map(raw_json)
    period_idx = _lookup_period(raw_json, local_dt)
    return period_map.get(period_idx, _FALLBACK_RATE)


def get_net_metering_credit(raw_json: dict) -> float:
    """Return the net metering export credit ($/kWh) from the URDB sell field."""
    structure = raw_json.get("energyratestructure") or []
    sells = []
    for tiers in structure:
        for tier in tiers:
            sell = tier.get("sell") or 0.0
            if sell > 0:
                sells.append(sell)
    return max(sells) if sells else 0.0


def summarise_periods(raw_json: dict) -> dict[str, float]:
    """Return {period_name: rate_usd_kwh} for display (deduped by period name)."""
    period_map = _build_period_map(raw_json)
    result: dict[str, float] = {}
    for _idx, (rate, name) in period_map.items():
        if name not in result or rate > result[name]:
            result[name] = rate
    return result
