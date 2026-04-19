"""Tests for backend.integrations.eia — carbon forecast client."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from backend.integrations.eia import (  # noqa: E402
    _build_forecast,
    _compute_intensity_by_hour,
    get_carbon_forecast,
)

# ---------------------------------------------------------------------------
# _compute_intensity_by_hour
# ---------------------------------------------------------------------------


class TestComputeIntensityByHour:
    def test_single_fuel_natural_gas(self):
        rows = [{"period": "2026-04-17T14", "fueltype": "NG", "value": 1000}]
        result = _compute_intensity_by_hour(rows)
        assert result["2026-04-17T14"] == pytest.approx(490.0)

    def test_mixed_hydro_and_wind(self):
        rows = [
            {"period": "2026-04-17T10", "fueltype": "WAT", "value": 800},
            {"period": "2026-04-17T10", "fueltype": "WND", "value": 200},
        ]
        result = _compute_intensity_by_hour(rows)
        # (800×4 + 200×11) / 1000 = 5.4
        assert result["2026-04-17T10"] == pytest.approx(5.4)

    def test_unknown_fuel_uses_other_factor(self):
        rows = [{"period": "2026-04-17T08", "fueltype": "UNKN", "value": 500}]
        result = _compute_intensity_by_hour(rows)
        assert result["2026-04-17T08"] == pytest.approx(300.0)  # "other" factor

    def test_zero_total_mw_returns_zero_not_crash(self):
        rows = [{"period": "2026-04-17T03", "fueltype": "NG", "value": 0}]
        result = _compute_intensity_by_hour(rows)
        assert result["2026-04-17T03"] == pytest.approx(0.0)

    def test_multiple_hours_are_independent(self):
        rows = [
            {"period": "2026-04-17T06", "fueltype": "WAT", "value": 1000},  # clean
            {"period": "2026-04-17T18", "fueltype": "NG", "value": 1000},  # dirty
        ]
        result = _compute_intensity_by_hour(rows)
        assert result["2026-04-17T06"] == pytest.approx(4.0)
        assert result["2026-04-17T18"] == pytest.approx(490.0)

    def test_none_value_treated_as_zero(self):
        rows = [
            {"period": "2026-04-17T05", "fueltype": "NG", "value": None},
            {"period": "2026-04-17T05", "fueltype": "WAT", "value": 500},
        ]
        result = _compute_intensity_by_hour(rows)
        assert result["2026-04-17T05"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# _build_forecast
# ---------------------------------------------------------------------------


class TestBuildForecast:
    def _base_intensity(self):
        """Intensity dict with 49 past hours of hydro-only data."""
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        return {(now - timedelta(hours=i)).strftime("%Y-%m-%dT%H"): 4.0 for i in range(50)}

    def test_returns_correct_length(self):
        result = _build_forecast(self._base_intensity(), datetime.now(UTC), 48)
        assert len(result) == 48

    def test_each_entry_has_required_keys(self):
        result = _build_forecast(self._base_intensity(), datetime.now(UTC), 24)
        for entry in result:
            assert "hour_utc" in entry
            assert "carbon_g_kwh" in entry

    def test_uses_yesterday_value_for_future_hours(self):
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        # Only populate yesterday's hours (24h ago), not future hours
        intensity = {
            (now - timedelta(hours=i)).strftime("%Y-%m-%dT%H"): 999.0 for i in range(1, 50)
        }
        # Future hour (i=5) should fall back to yesterday (i=5-24 = -19, which is in the past)
        result = _build_forecast(intensity, now, 48)
        assert result[5]["carbon_g_kwh"] == pytest.approx(999.0)

    def test_fallback_value_used_when_no_data(self):
        result = _build_forecast({}, datetime.now(UTC), 3)
        for entry in result:
            assert entry["carbon_g_kwh"] == pytest.approx(200.0)  # _FALLBACK_CARBON


# ---------------------------------------------------------------------------
# get_carbon_forecast (mocked HTTP)
# ---------------------------------------------------------------------------


class TestGetCarbonForecast:
    def _make_raw_response(self, n_hours: int = 10) -> dict:
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        rows = []
        for i in range(n_hours):
            period = (now - timedelta(hours=i)).strftime("%Y-%m-%dT%H")
            rows.append({"period": period, "fueltype": "WAT", "value": 1000})
        return {"response": {"data": rows}}

    @pytest.mark.asyncio
    async def test_returns_none_when_api_key_empty(self):
        result = await get_carbon_forecast(api_key="", hours=48)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_list_of_correct_length(self):
        with patch(
            "backend.integrations.eia._fetch_eia_raw",
            new_callable=AsyncMock,
            return_value=self._make_raw_response(49),
        ):
            # Clear module cache to avoid interference
            import backend.integrations.eia as eia_mod

            eia_mod._cache.clear()
            result = await get_carbon_forecast(api_key="test-key", hours=48)
        assert result is not None
        assert len(result) == 48

    @pytest.mark.asyncio
    async def test_each_entry_has_required_keys(self):
        with patch(
            "backend.integrations.eia._fetch_eia_raw",
            new_callable=AsyncMock,
            return_value=self._make_raw_response(49),
        ):
            import backend.integrations.eia as eia_mod

            eia_mod._cache.clear()
            result = await get_carbon_forecast(api_key="test-key", hours=24)
        assert result is not None
        for entry in result:
            assert "hour_utc" in entry
            assert "carbon_g_kwh" in entry

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        import httpx

        with patch(
            "backend.integrations.eia._fetch_eia_raw",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("connection refused"),
        ):
            import backend.integrations.eia as eia_mod

            eia_mod._cache.clear()
            result = await get_carbon_forecast(api_key="test-key", hours=48)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_prevents_second_http_call(self):
        with patch(
            "backend.integrations.eia._fetch_eia_raw",
            new_callable=AsyncMock,
            return_value=self._make_raw_response(49),
        ) as mock_fetch:
            import backend.integrations.eia as eia_mod

            eia_mod._cache.clear()
            await get_carbon_forecast(api_key="test-key", hours=48)
            await get_carbon_forecast(api_key="test-key", hours=48)
            assert mock_fetch.await_count == 1
