"""Tests for backend.engine.solar and backend.integrations.solar."""

from unittest.mock import AsyncMock, MagicMock, patch

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


# ---------------------------------------------------------------------------
# backend.integrations.solar — Open-Meteo primary + pvlib fallback
# ---------------------------------------------------------------------------

_MOCK_OPEN_METEO = {
    "hourly": {
        "time": [f"2024-01-01T{h:02d}:00" for h in range(48)],
        "direct_radiation": [float(i * 10) for i in range(48)],
        "diffuse_radiation": [float(i * 2) for i in range(48)],
    }
}


class TestGetSolarForecast:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        from backend.integrations import solar as solar_mod

        solar_mod._cache.clear()
        yield
        solar_mod._cache.clear()

    @pytest.mark.asyncio
    async def test_open_meteo_success_returns_48_hours(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=_MOCK_OPEN_METEO)

        with patch("backend.integrations.solar.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            from backend.integrations.solar import get_solar_forecast

            result = await get_solar_forecast(47.6, -122.3)

        assert result["source"] == "open-meteo"
        assert len(result["hourly"]) == 48
        assert result["hourly"][1]["direct_radiation_w_m2"] == pytest.approx(10.0)
        assert result["hourly"][1]["diffuse_radiation_w_m2"] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_open_meteo_failure_falls_back_to_pvlib(self):
        with patch("backend.integrations.solar.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            from backend.integrations.solar import get_solar_forecast

            result = await get_solar_forecast(47.6, -122.3)

        assert result["source"] == "pvlib-clearsky-fallback"
        assert len(result["hourly"]) == 48

    @pytest.mark.asyncio
    async def test_result_is_cached(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=_MOCK_OPEN_METEO)

        with patch("backend.integrations.solar.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            from backend.integrations.solar import get_solar_forecast

            await get_solar_forecast(47.6, -122.3)
            await get_solar_forecast(47.6, -122.3)

        # Should only have been called once despite two invocations
        assert mock_client.get.call_count == 1
