"""Tests for backend.engine.solar — solar power estimation."""

import pytest

from backend.engine.solar import estimate_net_metering_credit, estimate_power_from_irradiance


class TestEstimatePowerFromIrradiance:
    def test_zero_irradiance_returns_zero(self):
        result = estimate_power_from_irradiance(
            direct_w_m2=0,
            diffuse_w_m2=0,
            capacity_kw=10.0,
        )
        assert result == 0.0

    def test_output_capped_at_capacity(self):
        result = estimate_power_from_irradiance(
            direct_w_m2=5000,
            diffuse_w_m2=5000,
            capacity_kw=5.0,
        )
        assert result <= 5.0

    def test_output_non_negative(self):
        result = estimate_power_from_irradiance(
            direct_w_m2=-10,
            diffuse_w_m2=-10,
            capacity_kw=10.0,
        )
        assert result >= 0.0

    def test_standard_conditions_near_capacity(self):
        """At STC (1000 W/m² direct, flat panel, 80% efficiency) output ≈ 0.8 × capacity."""
        result = estimate_power_from_irradiance(
            direct_w_m2=1000,
            diffuse_w_m2=0,
            capacity_kw=10.0,
            tilt_deg=0.0,  # flat → cos(0) = 1.0
            efficiency=0.80,
        )
        assert result == pytest.approx(8.0, rel=0.01)

    def test_larger_system_produces_more(self):
        small = estimate_power_from_irradiance(500, 50, capacity_kw=5.0)
        large = estimate_power_from_irradiance(500, 50, capacity_kw=10.0)
        assert large > small

    def test_higher_efficiency_produces_more(self):
        low = estimate_power_from_irradiance(500, 50, capacity_kw=5.0, efficiency=0.70)
        high = estimate_power_from_irradiance(500, 50, capacity_kw=5.0, efficiency=0.90)
        assert high > low


class TestEstimateNetMeteringCredit:
    def test_no_export_when_solar_below_load(self):
        credit = estimate_net_metering_credit(solar_kw=1.0, load_kw=2.0, credit_rate=0.07)
        assert credit == pytest.approx(0.0)

    def test_full_export_when_no_load(self):
        credit = estimate_net_metering_credit(solar_kw=3.0, load_kw=0.0, credit_rate=0.07)
        assert credit == pytest.approx(0.21)  # 3 kWh × $0.07

    def test_partial_export(self):
        # 5 kW solar, 2 kW load → 3 kW exported × $0.07 = $0.21
        credit = estimate_net_metering_credit(solar_kw=5.0, load_kw=2.0, credit_rate=0.07)
        assert credit == pytest.approx(0.21)

    def test_zero_credit_rate(self):
        credit = estimate_net_metering_credit(solar_kw=5.0, load_kw=1.0, credit_rate=0.0)
        assert credit == pytest.approx(0.0)
