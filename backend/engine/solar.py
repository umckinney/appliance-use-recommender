"""
Solar generation estimator.

For users without SolarEdge (or when the SolarEdge API is unavailable),
estimate solar output from Open-Meteo irradiance data + system specs using pvlib.

For users WITH SolarEdge, actual measured output is used directly.
"""

from __future__ import annotations

import math


def estimate_power_from_irradiance(
    direct_w_m2: float,
    diffuse_w_m2: float,
    capacity_kw: float,
    tilt_deg: float = 20.0,
    azimuth_deg: float = 180.0,  # south-facing
    efficiency: float = 0.80,  # system efficiency (inverter + wiring losses)
) -> float:
    """
    Estimate solar panel output in kW from irradiance and system specs.

    Uses a simplified plane-of-array (POA) model:
    - Adjusts irradiance for panel tilt and azimuth
    - Applies system efficiency factor
    - Caps output at system capacity

    For production, swap with pvlib.irradiance.poa_components() for full accuracy.
    """
    if direct_w_m2 <= 0 and diffuse_w_m2 <= 0:
        return 0.0

    tilt_rad = math.radians(tilt_deg)

    # Simplified POA: direct component tilted, diffuse component isotropic
    # A more accurate model (pvlib) accounts for sun position; this is a fast approximation.
    poa_direct = direct_w_m2 * math.cos(tilt_rad)
    poa_diffuse = diffuse_w_m2 * (1 + math.cos(tilt_rad)) / 2  # isotropic sky
    poa_total = max(0.0, poa_direct + poa_diffuse)

    # Standard test condition is 1000 W/m² → capacity_kw output
    raw_kw = capacity_kw * (poa_total / 1000.0)
    return min(capacity_kw, raw_kw * efficiency)


def estimate_net_metering_credit(
    solar_kw: float,
    load_kw: float,
    credit_rate: float,
) -> float:
    """
    Calculate the net metering credit (USD) for one hour.

    If solar generation exceeds load, the excess is exported at credit_rate.
    If load exceeds solar, the deficit is covered by grid (no credit).
    """
    export_kw = max(0.0, solar_kw - load_kw)
    return export_kw * credit_rate  # credit for 1 hour (kWh = kW × 1h)
