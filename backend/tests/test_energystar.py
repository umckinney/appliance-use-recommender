"""Tests for backend.integrations.energystar."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.integrations.energystar import _normalize, search_models


class TestNormalize:
    def test_normalize_dishwasher(self):
        rows = [
            {
                "brand_name": "Bosch",
                "model_number": "SHX88PZ",
                "annual_energy_use_kwh_year": "234",
            }
        ]
        results = _normalize("dishwasher", rows, annual_cycles=215)
        assert len(results) == 1
        assert results[0]["brand"] == "Bosch"
        assert results[0]["model"] == "SHX88PZ"
        assert results[0]["cycle_kwh"] == pytest.approx(234 / 215, rel=1e-3)
        assert results[0]["cycle_minutes"] is None

    def test_normalize_dryer_includes_minutes(self):
        rows = [
            {
                "brand_name": "LG",
                "model_number": "DLGX7801VE",
                "estimated_annual_energy_use_kwh_yr": "566",
                "estimated_energy_test_cycle_time_min": "47",
            }
        ]
        results = _normalize("dryer", rows, annual_cycles=283)
        assert len(results) == 1
        assert results[0]["cycle_minutes"] == 47

    def test_normalize_dryer_missing_time_is_none(self):
        rows = [
            {
                "brand_name": "GE",
                "model_number": "GTD42EASJWW",
                "estimated_annual_energy_use_kwh_yr": "590",
            }
        ]
        results = _normalize("dryer", rows, annual_cycles=283)
        assert results[0]["cycle_minutes"] is None

    def test_normalize_skips_row_without_energy(self):
        rows = [{"brand_name": "Mystery", "model_number": "X1"}]
        results = _normalize("dishwasher", rows, annual_cycles=215)
        assert len(results) == 0

    def test_normalize_skips_row_without_brand_or_model(self):
        rows = [{"annual_energy_use_kwh_year": "234"}]
        results = _normalize("dishwasher", rows, annual_cycles=215)
        assert len(results) == 0


class TestSearchModels:
    @pytest.mark.asyncio
    async def test_unknown_category_raises(self):
        with pytest.raises(ValueError, match="Unsupported category"):
            await search_models("hot_tub", "spa brand")

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_http_error(self):
        with patch(
            "backend.integrations.energystar._fetch_raw",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPError("timeout"),
        ):
            results = await search_models("dishwasher", "bosch")
        assert results == []

    @pytest.mark.asyncio
    async def test_cache_prevents_second_call(self):
        mock_rows = [
            {
                "brand_name": "Bosch",
                "model_number": "SMS68",
                "estimated_annual_energy_use_kwh": "240",
            }
        ]
        # Clear any stale cache entry first
        from backend.integrations import energystar as es

        es._CACHE.clear()

        with patch(
            "backend.integrations.energystar._fetch_raw",
            new_callable=AsyncMock,
            return_value=mock_rows,
        ) as mock_fetch:
            await search_models("dishwasher", "bosch_cache_test", limit=5)
            await search_models("dishwasher", "bosch_cache_test", limit=5)

        mock_fetch.assert_called_once()
