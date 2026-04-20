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
MOCK_GEO = {
    "lat": 47.6062,
    "lon": -122.3321,
    "display_name": "Seattle, WA",
    "country_code": "us",
    "postcode": "98101",
    "precise": True,
}


# ---------------------------------------------------------------------------
# /onboard
# ---------------------------------------------------------------------------


class TestOnboard:
    @pytest.mark.asyncio
    async def test_onboard_creates_user_and_returns_api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
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
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
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
        _no_location = {
            "lat": None,
            "lon": None,
            "display_name": "",
            "country_code": "",
            "postcode": "",
            "precise": False,
            "fallback_reason": "Could not determine your location.",
        }
        with patch(
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=_no_location,
        ):
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
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
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
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
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
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
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
                "backend.routers.recommend.solar_integration.get_solar_forecast",
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
                "backend.routers.recommend.solar_integration.get_solar_forecast",
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
                "backend.routers.recommend.solar_integration.get_solar_forecast",
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
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
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
                "backend.routers.forecast.solar_integration.get_solar_forecast",
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
                "backend.routers.forecast.solar_integration.get_solar_forecast",
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
                "backend.routers.forecast.solar_integration.get_solar_forecast",
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
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
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


# ---------------------------------------------------------------------------
# /account
# ---------------------------------------------------------------------------


class TestAccount:
    @pytest.fixture
    async def api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
        ):
            resp = await client.post(
                "/onboard",
                json={"address": "123 Main St, Seattle WA", "utility_id": "seattle_city_light"},
            )
        return resp.json()["api_key"]

    @pytest.mark.asyncio
    async def test_update_preferences_stores_weight(self, client, api_key):
        resp = await client.patch(
            f"/account/preferences?api_key={api_key}",
            json={"optimization_weight": 0.0},
        )
        assert resp.status_code == 200
        assert resp.json()["optimization_weight"] == 0.0

    @pytest.mark.asyncio
    async def test_update_preferences_invalid_key_returns_401(self, client):
        resp = await client.patch(
            "/account/preferences?api_key=bad-key",
            json={"optimization_weight": 0.5},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_update_preferences_out_of_range_returns_422(self, client, api_key):
        resp = await client.patch(
            f"/account/preferences?api_key={api_key}",
            json={"optimization_weight": 1.5},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /recommend/all
# ---------------------------------------------------------------------------


class TestRecommendAll:
    @pytest.fixture
    async def api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "address": "123 Main St, Seattle WA",
                    "utility_id": "seattle_city_light",
                    "appliances": [
                        {
                            "name": "Dishwasher",
                            "slug": "dishwasher",
                            "cycle_kwh": 1.5,
                            "cycle_minutes": 90,
                        },
                        {"name": "Dryer", "slug": "dryer", "cycle_kwh": 5.0, "cycle_minutes": 60},
                    ],
                },
            )
        return resp.json()["api_key"]

    @pytest.mark.asyncio
    async def test_recommend_all_returns_shared_window(self, client, api_key):
        with (
            patch(
                "backend.routers.recommend.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.recommend.solar_integration.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.recommend.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await client.get(f"/recommend/all?api_key={api_key}")

        assert resp.status_code == 200
        body = resp.json()
        assert "text" in body
        assert "best_shared_start" in body
        assert len(body["per_appliance"]) == 2

    @pytest.mark.asyncio
    async def test_recommend_all_no_appliances_returns_404(self, client, api_key):
        # Delete all appliances so the user has none
        appliances = (await client.get(f"/appliances?api_key={api_key}")).json()
        for a in appliances:
            await client.delete(f"/appliances/{a['slug']}?api_key={api_key}")

        with (
            patch(
                "backend.routers.recommend.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.recommend.solar_integration.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.recommend.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await client.get(f"/recommend/all?api_key={api_key}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /shortcuts
# ---------------------------------------------------------------------------


class TestShortcuts:
    @pytest.fixture
    async def api_key(self, client):
        with patch(
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "address": "789 Main St, Seattle WA",
                    "utility_id": "seattle_city_light",
                    "appliances": [
                        {
                            "name": "Dishwasher",
                            "slug": "dishwasher",
                            "cycle_kwh": 1.5,
                            "cycle_minutes": 90,
                        },
                    ],
                },
            )
        return resp.json()["api_key"]

    @pytest.mark.asyncio
    async def test_shortcut_download_returns_plist(self, client, api_key):
        resp = await client.get(f"/shortcuts/dishwasher?api_key={api_key}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"
        assert ".shortcut" in resp.headers["content-disposition"]
        assert resp.content[:8] == b"bplist00"

    @pytest.mark.asyncio
    async def test_shortcut_all_returns_plist(self, client, api_key):
        resp = await client.get(f"/shortcuts/all?api_key={api_key}")
        assert resp.status_code == 200
        assert resp.content[:8] == b"bplist00"

    @pytest.mark.asyncio
    async def test_shortcut_unknown_slug_returns_404(self, client, api_key):
        resp = await client.get(f"/shortcuts/nonexistent?api_key={api_key}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_shortcut_invalid_key_returns_401(self, client):
        resp = await client.get("/shortcuts/dishwasher?api_key=bad-key")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# get_ba_code + EIA ba_code propagation
# ---------------------------------------------------------------------------


class TestBalancingAuthority:
    def test_get_ba_code_returns_bpat_for_seattle(self):
        from backend.engine.rates import get_ba_code

        assert get_ba_code("seattle_city_light") == "BPAT"

    def test_get_ba_code_returns_none_for_unknown_utility(self):
        from backend.engine.rates import get_ba_code

        assert get_ba_code("nonexistent_utility") is None

    @pytest.mark.asyncio
    async def test_recommend_passes_ba_code_to_eia(self, client):
        """EIA get_carbon_forecast should be called with the utility's BA code."""
        with patch(
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
        ):
            resp = await client.post(
                "/onboard",
                json={
                    "address": "500 Pike St, Seattle, WA",
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
        api_key = resp.json()["api_key"]

        eia_mock = AsyncMock(return_value=None)
        with (
            patch(
                "backend.routers.recommend.bpa.get_carbon_intensity",
                new_callable=AsyncMock,
                return_value=MOCK_GRID,
            ),
            patch(
                "backend.routers.recommend.solar_integration.get_solar_forecast",
                new_callable=AsyncMock,
                return_value=MOCK_WEATHER,
            ),
            patch(
                "backend.routers.recommend.solaredge.get_current_power",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("backend.routers.recommend.eia.get_carbon_forecast", eia_mock),
            patch("backend.routers.recommend.settings.eia_api_key", new="test-key"),
        ):
            await client.get(f"/recommend/dishwasher?api_key={api_key}")

        eia_mock.assert_called_once()
        _, kwargs = eia_mock.call_args
        assert kwargs.get("ba_code") == "BPAT"


# ---------------------------------------------------------------------------
# /auth — magic link + session
# ---------------------------------------------------------------------------


class TestAuth:
    """Helper shared by tests that need to insert a magic link token directly."""

    async def _insert_token(self, db_factory, email: str, raw_token: str) -> None:
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import select

        from backend.models import MagicLinkToken, User
        from backend.routers.auth import _hash_token

        async with db_factory() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            db.add(
                MagicLinkToken(
                    user_id=user.id,
                    token_hash=_hash_token(raw_token),
                    expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=15),
                )
            )
            await db.commit()

    async def _onboard(self, client, email: str) -> None:
        with patch(
            "backend.routers.onboard.geocode_with_fallback",
            new_callable=AsyncMock,
            return_value=MOCK_GEO,
        ):
            await client.post(
                "/onboard",
                json={"email": email, "address": "1 Main St", "utility_id": "seattle_city_light"},
            )

    @pytest.mark.asyncio
    async def test_magic_link_send_enumeration_safe(self, client):
        """Always returns 200 regardless of whether email exists."""
        resp = await client.post(
            "/auth/magic-link/send",
            json={"email": "nobody@example.com"},
        )
        assert resp.status_code == 200
        assert "sign-in link" in resp.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_magic_link_verify_invalid_token(self, client):
        resp = await client.get("/auth/magic-link/verify?token=badtoken")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_magic_link_full_flow(self, client, db_factory):
        """Create a user, issue a magic link token, verify it, check session cookie."""
        await self._onboard(client, "magic@example.com")
        await self._insert_token(db_factory, "magic@example.com", "test-magic-token-abc123")

        resp = await client.get(
            "/auth/magic-link/verify?token=test-magic-token-abc123",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "dashboard" in resp.headers["location"]
        assert resp.cookies.get("fs_session") is not None

    @pytest.mark.asyncio
    async def test_magic_link_token_single_use(self, client, db_factory):
        """Verifying the same token twice should fail on the second attempt."""
        await self._onboard(client, "once@example.com")
        await self._insert_token(db_factory, "once@example.com", "single-use-token-xyz")

        r1 = await client.get("/auth/magic-link/verify?token=single-use-token-xyz", follow_redirects=False)
        assert r1.status_code in (302, 307)

        r2 = await client.get("/auth/magic-link/verify?token=single-use-token-xyz", follow_redirects=False)
        assert r2.status_code == 400

    @pytest.mark.asyncio
    async def test_me_unauthenticated(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_session(self, client, db_factory):
        """After magic link verify, /auth/me should return user info."""
        await self._onboard(client, "me@example.com")
        await self._insert_token(db_factory, "me@example.com", "me-test-token")

        verify = await client.get("/auth/magic-link/verify?token=me-test-token", follow_redirects=False)
        assert verify.status_code in (302, 307)

        me = await client.get("/auth/me")
        assert me.status_code == 200
        data = me.json()
        assert data["email"] == "me@example.com"
        assert "api_key" in data

    @pytest.mark.asyncio
    async def test_logout_clears_session(self, client, db_factory):
        """After logout, /auth/me should return 401."""
        await self._onboard(client, "logout@example.com")
        await self._insert_token(db_factory, "logout@example.com", "logout-test-token")

        await client.get("/auth/magic-link/verify?token=logout-test-token", follow_redirects=False)
        assert (await client.get("/auth/me")).status_code == 200

        await client.post("/auth/logout")
        assert (await client.get("/auth/me")).status_code == 401

    @pytest.mark.asyncio
    async def test_oauth_login_unknown_provider(self, client):
        resp = await client.get("/auth/unknown-provider/login")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_oauth_callback_state_mismatch(self, client):
        resp = await client.get(
            "/auth/google/callback?code=abc&state=wrong",
            follow_redirects=False,
        )
        assert resp.status_code == 400
