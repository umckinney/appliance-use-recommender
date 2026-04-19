"""
Schedule optimizer — finds the best windows to run an appliance over the next 24–48h.

For each hour, computes:
  net_cost_usd  = (cycle_kwh × rate) - net_metering_credit
  carbon_kg     = cycle_kwh × carbon_g_kwh / 1000
  score         = (1 - weight) × normalized_cost + weight × normalized_carbon

Returns the ranked list of windows (lowest score = best).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Window:
    hour_utc: str
    hour_local: str
    rate_usd_kwh: float
    carbon_g_kwh: float
    solar_kw: float
    net_cost_usd: float
    carbon_kg: float
    score: float


def score_windows(
    rate_schedule: list[dict],  # from engine.rates.get_24h_schedule()
    carbon_forecast: list[dict],  # [{"hour_local": str, "carbon_g_kwh": float}, ...]
    solar_forecast: list[float],  # [kW per hour], same length as rate_schedule
    appliance_kwh: float,
    net_metering_credit_rate: float,  # USD/kWh exported
    optimization_weight: float,  # 0=minimize cost, 1=minimize carbon
    base_load_kw: float = 0.5,  # assumed background load for net metering calc
) -> list[Window]:
    """
    Score each hour in the schedule and return sorted windows (best first).
    """
    n = min(len(rate_schedule), len(carbon_forecast), len(solar_forecast))
    windows: list[Window] = []

    for i in range(n):
        rate = rate_schedule[i]["rate_usd_kwh"]
        carbon = carbon_forecast[i]["carbon_g_kwh"] if i < len(carbon_forecast) else 200.0
        solar = solar_forecast[i] if i < len(solar_forecast) else 0.0

        # Net metering: if solar > background load, surplus offsets appliance cost
        surplus_kw = max(0.0, solar - base_load_kw)
        # Fraction of appliance cycle covered by solar export credit
        credit_kwh = min(appliance_kwh, surplus_kw)
        net_cost = (appliance_kwh * rate) - (credit_kwh * net_metering_credit_rate)
        net_cost = max(0.0, net_cost)

        grid_kwh = max(0.0, appliance_kwh - surplus_kw)
        carbon_kg = grid_kwh * carbon / 1000.0

        windows.append(
            Window(
                hour_utc=rate_schedule[i].get("hour_utc", rate_schedule[i]["hour_local"]),
                hour_local=rate_schedule[i]["hour_local"],
                rate_usd_kwh=rate,
                carbon_g_kwh=carbon,
                solar_kw=solar,
                net_cost_usd=round(net_cost, 4),
                carbon_kg=round(carbon_kg, 4),
                score=0.0,  # filled below
            )
        )

    # Normalize cost and carbon independently, then combine with weight
    costs = [w.net_cost_usd for w in windows]
    carbons = [w.carbon_kg for w in windows]
    c_min, c_max = min(costs), max(costs)
    k_min, k_max = min(carbons), max(carbons)

    for w in windows:
        norm_cost = (w.net_cost_usd - c_min) / (c_max - c_min + 1e-9)
        norm_carbon = (w.carbon_kg - k_min) / (k_max - k_min + 1e-9)
        w.score = round(
            (1 - optimization_weight) * norm_cost + optimization_weight * norm_carbon, 4
        )

    return sorted(windows, key=lambda w: w.score)


def carbon_label(g_kwh: float) -> str:
    """Human-readable label for grid carbon intensity."""
    if g_kwh < 50:
        return "very clean"
    if g_kwh < 150:
        return "clean"
    if g_kwh < 300:
        return "moderate"
    if g_kwh < 500:
        return "dirty"
    return "very dirty"


def build_recommendation_text(
    appliance_name: str,
    best: Window,
    current: Window,
    best_windows: list[Window],
) -> str:
    """
    Generate a natural-language recommendation suitable for Siri/HomePod speech.
    Short, clear, and actionable.
    """

    def fmt_time(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso)
            return dt.strftime("%-I %p").lower()  # e.g. "10 pm"
        except Exception:
            return iso

    best_time = fmt_time(best.hour_local)
    cost_save = current.net_cost_usd - best.net_cost_usd
    carbon_save = current.carbon_kg - best.carbon_kg

    # If best is the current hour, say so
    if best.score == current.score:
        return (
            f"Now is actually a good time to run the {appliance_name}. "
            f"The grid is {carbon_label(current.carbon_g_kwh)} "
            f"and it will cost about {current.net_cost_usd:.0f} cents."
        )

    parts = [f"Best time to run the {appliance_name} is {best_time}."]

    if cost_save > 0.005:
        parts.append(f"That saves about {cost_save * 100:.0f} cents versus now.")
    if carbon_save > 0.01:
        parts.append(f"The grid will be {carbon_label(best.carbon_g_kwh)} at that time.")

    return " ".join(parts)
