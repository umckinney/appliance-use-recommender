"""Integration tests for FlowShift API routes.

External API calls (BPA, SolarEdge, Open-Meteo) are mocked so tests run
offline and deterministically.
"""

from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

MOCK_GRID = {"carbon_g_kwh": 150.0, "zone": "BPA", "total_mw": 8500}
MOCK_WEATHER = {"hourly": [{"direct_radiation_w_m2": 500, "diffuse_radiation_w_m2": 100}] * 48}
MOCK_GEO = {"lat": 47.6062, "lon": -122.3321, "timezone": "America/Los_Angeles"}


# ---------------------------------------------------------------------------
# /onboard
# ---------------------------------------------------------------------------


class TestOnboard:
    @pytest.mark.asyncio
    async def test_onboard_creates_user_and_returns_api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode", new_callable=AsyncMock, return_value=MOCK_GEO
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "name": "Test User",
                    "email": "test@example.com",
                    "address": "123 Main St, Seattle, WA",
                    "utility_id": "seattle_city_light",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "api_key" in body
        assert len(body["api_key"]) >= 32  # token_urlsafe(32) → 43 base64url chars
        assert "FlowShift" in body["message"] or "Welcome" in body["message"]

    @pytest.mark.asyncio
    async def test_onboard_idempotent_same_email(self, client):
        """Calling /onboard twice with the same email updates the user, same API key."""
        with patch(
            "backend.routers.onboard.geocode", new_callable=AsyncMock, return_value=MOCK_GEO
        ):
            r1 = await client.post(
                "/onboard",
                json={
                    "email": "idem@example.com",
                    "address": "456 Pine St, Seattle, WA",
                    "utility_id": "seattle_city_light",
                },
            )
            r2 = await client.post(
                "/onboard",
                json={
                    "name": "Updated Name",
                    "email": "idem@example.com",
                    "address": "456 Pine St, Seattle, WA",
                    "utility_id": "seattle_city_light",
                },
            )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["api_key"] == r2.json()["api_key"]

    @pytest.mark.asyncio
    async def test_onboard_bad_address_returns_422(self, client):
        with patch("backend.routers.onboard.geocode", new_callable=AsyncMock, return_value=None):
            resp = await client.post(
                "/onboard",
                json={
                    "address": "not a real place xyz",
                    "utility_id": "seattle_city_light",
                },
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_creates_default_appliance(self, client):
        with patch(
            "backend.routers.onboard.geocode", new_callable=AsyncMock, return_value=MOCK_GEO
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "address": "789 Oak Ave, Seattle, WA",
                    "utility_id": "seattle_city_light",
                },
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /appliances
# ---------------------------------------------------------------------------


class TestAppliances:
    @pytest.fixture
    async def api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode", new_callable=AsyncMock, return_value=MOCK_GEO
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "email": "appliance_user@example.com",
                    "address": "1 Test St, Seattle, WA",
                    "utility_id": "seattle_city_light",
                },
            )
        return resp.json()["api_key"]

    @pytest.mark.asyncio
    async def test_list_appliances(self, client, api_key):
        resp = await client.get(f"/appliances?api_key={api_key}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_add_appliance(self, client, api_key):
        resp = await client.post(
            f"/appliances?api_key={api_key}",
            json={
                "name": "Pool Pump",
                "slug": "pool_pump",
                "cycle_kwh": 1.5,
                "cycle_minutes": 60,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["slug"] == "pool_pump"
        assert body["cycle_kwh"] == 1.5

    @pytest.mark.asyncio
    async def test_add_appliance_upsert(self, client, api_key):
        """Adding the same slug twice should update, not duplicate."""
        payload = {
            "name": "Dryer",
            "slug": "dryer",
            "cycle_kwh": 5.0,
            "cycle_minutes": 60,
        }
        await client.post(f"/appliances?api_key={api_key}", json=payload)
        payload["cycle_kwh"] = 4.5
        resp = await client.post(f"/appliances?api_key={api_key}", json=payload)
        assert resp.status_code == 201
        assert resp.json()["cycle_kwh"] == 4.5

        # Should still be only one dryer
        listing = await client.get(f"/appliances?api_key={api_key}")
        dryers = [a for a in listing.json() if a["slug"] == "dryer"]
        assert len(dryers) == 1

    @pytest.mark.asyncio
    async def test_delete_appliance(self, client, api_key):
        await client.post(
            f"/appliances?api_key={api_key}",
            json={"name": "EV", "slug": "ev_charger", "cycle_kwh": 25.0, "cycle_minutes": 240},
        )
        resp = await client.delete(f"/appliances/ev_charger?api_key={api_key}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_appliance_returns_404(self, client, api_key):
        resp = await client.delete(f"/appliances/ghost_appliance?api_key={api_key}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self, client):
        resp = await client.get("/appliances?api_key=invalid")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_presets_no_auth(self, client):
        resp = await client.get("/appliances/presets")
        assert resp.status_code == 200
        presets = resp.json()
        slugs = [p["slug"] for p in presets]
        assert "dishwasher" in slugs


# ---------------------------------------------------------------------------
# /recommend
# ---------------------------------------------------------------------------


class TestRecommend:
    @pytest.fixture
    async def api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode", new_callable=AsyncMock, return_value=MOCK_GEO
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "email": "recommend_user@example.com",
                    "address": "1 Test St, Seattle, WA",
                    "utility_id": "seattle_city_light",
                    "appliances": [
                        {
                            "name": "Dishwasher",
                            "slug": "dishwasher",
                            "cycle_kwh": 1.5,
                            "cycle_minutes": 90,
                        }
                    ],
                },
            )
        return resp.json()["api_key"]

    @pytest.mark.asyncio
    async def test_recommend_returns_response(self, client, api_key):
        with (
            patch(
                "backend.routers.recommend.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.recommend.open_meteo.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.recommend.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await client.get(f"/recommend/dishwasher?api_key={api_key}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["appliance"] == "Dishwasher"
        assert isinstance(body["text"], str) and len(body["text"]) > 0
        assert len(body["best_windows"]) > 0
        assert "current_window" in body
        assert "cost_now_usd" in body

    @pytest.mark.asyncio
    async def test_recommend_unknown_appliance_returns_404(self, client, api_key):
        with (
            patch(
                "backend.routers.recommend.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.recommend.open_meteo.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.recommend.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await client.get(f"/recommend/hot_tub?api_key={api_key}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_recommend_invalid_key_returns_401(self, client):
        resp = await client.get("/recommend/dishwasher?api_key=bad")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_recommend_uses_eia_forecast_when_available(self, client, api_key):
        """When EIA returns varied carbon data, best_windows should show differing carbon values."""
        varying_carbon = [
            {"hour_utc": f"2026-01-01T{i:02d}:00:00", "carbon_g_kwh": float(10 + i * 20)}
            for i in range(48)
        ]
        with (
            patch(
                "backend.routers.recommend.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.recommend.open_meteo.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.recommend.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.routers.recommend.eia.get_carbon_forecast",
                new_callable=AsyncMock,
                return_value=varying_carbon,
            ),
            patch(
                "backend.routers.recommend.settings.eia_api_key",
                new="test-key",
            ),
        ):
            resp = await client.get(f"/recommend/dishwasher?api_key={api_key}")

        assert resp.status_code == 200
        body = resp.json()
        carbon_values = {w["carbon_g_kwh"] for w in body["best_windows"]}
        assert (
            len(carbon_values) > 1
        ), "EIA forecast should produce varying carbon values across windows"
        assert "EIA" in " ".join(body["data_sources"])


# ---------------------------------------------------------------------------
# /forecast
# ---------------------------------------------------------------------------


class TestForecast:
    @pytest.fixture
    async def api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode", new_callable=AsyncMock, return_value=MOCK_GEO
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "email": "forecast_user@example.com",
                    "address": "1 Test St, Seattle, WA",
                    "utility_id": "seattle_city_light",
                },
            )
        return resp.json()["api_key"]

    @pytest.mark.asyncio
    async def test_forecast_returns_24_hours(self, client, api_key):
        with (
            patch(
                "backend.routers.forecast.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.forecast.open_meteo.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.forecast.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await client.get(f"/forecast?api_key={api_key}")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["hours"]) == 24
        assert "best_window_start" in body

    @pytest.mark.asyncio
    async def test_forecast_flat_carbon_without_eia(self, client, api_key):
        """Without EIA key, all hours should have the same BPA carbon value."""
        with (
            patch(
                "backend.routers.forecast.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.forecast.open_meteo.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.forecast.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.routers.forecast.settings.eia_api_key",
                new=None,
            ),
        ):
            resp = await client.get(f"/forecast?api_key={api_key}")
        body = resp.json()
        carbon_values = {h["carbon_g_kwh"] for h in body["hours"]}
        assert carbon_values == {150.0}  # BPA flat-repeat

    @pytest.mark.asyncio
    async def test_forecast_varying_carbon_with_eia(self, client, api_key):
        """EIA forecast should produce per-hour carbon values in the forecast response."""
        eia_data = [
            {"hour_utc": f"2026-01-01T{i:02d}:00:00", "carbon_g_kwh": float(i * 10)}
            for i in range(48)
        ]
        with (
            patch(
                "backend.routers.forecast.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.forecast.open_meteo.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.forecast.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.routers.forecast.eia.get_carbon_forecast",
                new_callable=AsyncMock,
                return_value=eia_data,
            ),
            patch(
                "backend.routers.forecast.settings.eia_api_key",
                new="test-key",
            ),
        ):
            resp = await client.get(f"/forecast?api_key={api_key}")
        body = resp.json()
        carbon_values = {h["carbon_g_kwh"] for h in body["hours"]}
        assert len(carbon_values) > 1, "EIA forecast should produce varied carbon per hour"


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------


class TestStatus:
    @pytest.fixture
    async def api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode", new_callable=AsyncMock, return_value=MOCK_GEO
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "email": "status_user@example.com",
                    "address": "1 Test St, Seattle, WA",
                    "utility_id": "seattle_city_light",
                },
            )
        return resp.json()["api_key"]

    @pytest.mark.asyncio
    async def test_status_returns_snapshot(self, client, api_key):
        with (
            patch(
                "backend.routers.status.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.status.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await client.get(f"/status?api_key={api_key}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["carbon_intensity_g_kwh"] == 150.0
        assert body["carbon_label"] == "moderate"  # 150 g/kWh hits the ≥150 boundary
        assert body["solar_kw"] is None
        assert "current_rate_usd_kwh" in body
        assert "rate_period" in body
