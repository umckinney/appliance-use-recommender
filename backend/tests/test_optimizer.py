"""Tests for backend.engine.optimizer — score_windows and build_recommendation_text."""

import pytest

from backend.engine.optimizer import (
    Window,
    build_recommendation_text,
    carbon_label,
    score_windows,
)


def _make_schedule(n: int, rate: float = 0.10) -> list[dict]:
    return [{"hour_local": f"2026-01-01T{i:02d}:00:00", "rate_usd_kwh": rate} for i in range(n)]


def _make_carbon(n: int, g_kwh: float = 200.0) -> list[dict]:
    return [{"carbon_g_kwh": g_kwh}] * n


class TestScoreWindows:
    def test_returns_one_window_per_hour(self):
        schedule = _make_schedule(6)
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(6),
            solar_forecast=[0.0] * 6,
            appliance_kwh=1.5,
            net_metering_credit_rate=0.0,
            optimization_weight=0.5,
        )
        assert len(windows) == 6

    def test_sorted_best_first(self):
        # Varying rates: hour 3 is cheapest
        schedule = _make_schedule(4, rate=0.20)
        schedule[3]["rate_usd_kwh"] = 0.05
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(4),
            solar_forecast=[0.0] * 4,
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.0,  # cost only
        )
        assert windows[0].rate_usd_kwh == pytest.approx(0.05)

    def test_net_cost_calculation(self):
        schedule = [{"hour_local": "2026-01-01T10:00:00", "rate_usd_kwh": 0.10}]
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(1),
            solar_forecast=[0.0],
            appliance_kwh=2.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.0,
        )
        assert windows[0].net_cost_usd == pytest.approx(0.20)

    def test_net_metering_reduces_cost(self):
        """Surplus solar should reduce net cost via export credit."""
        schedule = [{"hour_local": "2026-01-01T12:00:00", "rate_usd_kwh": 0.10}]
        # Solar 3 kW, base load 0.5 kW → surplus 2.5 kW > appliance 1.5 kWh
        # credit = min(1.5, 2.5) × 0.07 = 0.105; net = 0.15 - 0.105 = 0.045
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(1),
            solar_forecast=[3.0],
            appliance_kwh=1.5,
            net_metering_credit_rate=0.07,
            optimization_weight=0.0,
        )
        assert windows[0].net_cost_usd == pytest.approx(0.045, abs=1e-4)

    def test_net_cost_never_negative(self):
        """Net cost should be clamped to zero even with large solar surplus."""
        schedule = [{"hour_local": "2026-01-01T12:00:00", "rate_usd_kwh": 0.05}]
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(1),
            solar_forecast=[100.0],  # massive surplus
            appliance_kwh=1.0,
            net_metering_credit_rate=1.0,  # huge credit rate
            optimization_weight=0.0,
        )
        assert windows[0].net_cost_usd >= 0.0

    def test_carbon_kg_calculation(self):
        schedule = [{"hour_local": "2026-01-01T10:00:00", "rate_usd_kwh": 0.10}]
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=[{"carbon_g_kwh": 400.0}],
            solar_forecast=[0.0],
            appliance_kwh=2.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.5,
        )
        # 2.0 kWh × 400 g/kWh / 1000 = 0.8 kg
        assert windows[0].carbon_kg == pytest.approx(0.8)

    def test_score_weight_zero_ignores_carbon(self):
        """weight=0 → score driven purely by cost; carbon variation has no effect."""
        schedule = _make_schedule(2, rate=0.10)
        carbon = [{"carbon_g_kwh": 10.0}, {"carbon_g_kwh": 900.0}]
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=carbon,
            solar_forecast=[0.0, 0.0],
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.0,
        )
        # Both hours have identical cost → both should have score 0
        assert windows[0].score == pytest.approx(0.0)
        assert windows[1].score == pytest.approx(0.0)

    def test_score_weight_one_ignores_cost(self):
        """weight=1 → score driven purely by carbon; cheapest hour is irrelevant."""
        schedule = [
            {"hour_local": "2026-01-01T08:00:00", "rate_usd_kwh": 0.05},  # cheap, dirty
            {"hour_local": "2026-01-01T09:00:00", "rate_usd_kwh": 0.20},  # expensive, clean
        ]
        carbon = [{"carbon_g_kwh": 800.0}, {"carbon_g_kwh": 50.0}]
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=carbon,
            solar_forecast=[0.0, 0.0],
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=1.0,
        )
        # Clean hour should be ranked first
        assert windows[0].carbon_g_kwh == pytest.approx(50.0)

    def test_uniform_inputs_produce_zero_scores(self):
        """When all hours are identical, all scores should be 0."""
        schedule = _make_schedule(4)
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(4),
            solar_forecast=[0.0] * 4,
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.5,
        )
        for w in windows:
            assert w.score == pytest.approx(0.0, abs=1e-6)

    def test_solar_surplus_eliminates_carbon(self):
        """When solar fully covers the appliance, carbon_kg should be zero."""
        schedule = [{"hour_local": "2026-01-01T12:00:00", "rate_usd_kwh": 0.10}]
        # solar 5 kW, base_load 0.5 kW → surplus 4.5 kW > appliance 1.5 kWh → grid_kwh = 0
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=[{"carbon_g_kwh": 400.0}],
            solar_forecast=[5.0],
            appliance_kwh=1.5,
            net_metering_credit_rate=0.07,
            optimization_weight=0.5,
        )
        assert windows[0].carbon_kg == pytest.approx(0.0)

    def test_partial_solar_reduces_carbon_proportionally(self):
        """Partial solar surplus should reduce carbon by the solar-covered fraction."""
        schedule = [{"hour_local": "2026-01-01T12:00:00", "rate_usd_kwh": 0.10}]
        # solar 1.5 kW, base_load 0.5 kW → surplus 1.0 kW; appliance 2.0 kWh
        # grid_kwh = max(0, 2.0 - 1.0) = 1.0 → carbon = 1.0 × 400 / 1000 = 0.4 kg
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=[{"carbon_g_kwh": 400.0}],
            solar_forecast=[1.5],
            appliance_kwh=2.0,
            net_metering_credit_rate=0.07,
            optimization_weight=0.5,
        )
        assert windows[0].carbon_kg == pytest.approx(0.4)

    def test_no_solar_carbon_unchanged(self):
        """With zero solar, carbon_kg should equal appliance_kwh × carbon / 1000."""
        schedule = [{"hour_local": "2026-01-01T10:00:00", "rate_usd_kwh": 0.10}]
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=[{"carbon_g_kwh": 400.0}],
            solar_forecast=[0.0],
            appliance_kwh=2.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.5,
        )
        assert windows[0].carbon_kg == pytest.approx(0.8)

    def test_minimum_length_used_across_inputs(self):
        """If inputs have different lengths, output length = min of all three."""
        schedule = _make_schedule(10)
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(5),
            solar_forecast=[0.0] * 8,
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.5,
        )
        assert len(windows) == 5

    def test_multi_hour_span_averages_rate(self):
        """3-hour cycle starting at hour 0 with rates [0.05, 0.20, 0.20] → avg 0.15, not 0.05."""
        schedule = [
            {"hour_local": f"2026-01-01T{i:02d}:00:00", "rate_usd_kwh": r}
            for i, r in enumerate([0.05, 0.20, 0.20])
        ]
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(3),
            solar_forecast=[0.0] * 3,
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.0,
            cycle_minutes=180,
        )
        # Hour 0 window spans hours 0-2: avg rate = (0.05+0.20+0.20)/3 = 0.15
        hour0_window = next(w for w in windows if "T00:" in w.hour_local)
        assert hour0_window.rate_usd_kwh == pytest.approx(0.15, rel=1e-4)

    def test_single_hour_cycle_unchanged(self):
        """cycle_minutes=60 should behave identically to the default (no span averaging)."""
        schedule = _make_schedule(4, rate=0.10)
        schedule[2]["rate_usd_kwh"] = 0.05

        default_windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(4),
            solar_forecast=[0.0] * 4,
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.0,
        )
        explicit_windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(4),
            solar_forecast=[0.0] * 4,
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.0,
            cycle_minutes=60,
        )
        assert [w.hour_local for w in default_windows] == [w.hour_local for w in explicit_windows]

    def test_span_clips_at_schedule_end(self):
        """Cycle starting at the last available hour should not crash; clips to available hours."""
        schedule = _make_schedule(3)
        windows = score_windows(
            rate_schedule=schedule,
            carbon_forecast=_make_carbon(3),
            solar_forecast=[0.0] * 3,
            appliance_kwh=1.0,
            net_metering_credit_rate=0.0,
            optimization_weight=0.5,
            cycle_minutes=180,  # 3-hour span, last hour has only 1 available
        )
        assert len(windows) == 3  # should not crash or skip any windows


class TestCarbonLabel:
    @pytest.mark.parametrize(
        "g_kwh,expected",
        [
            (20, "very clean"),
            (49, "very clean"),
            (50, "clean"),
            (149, "clean"),
            (150, "moderate"),
            (299, "moderate"),
            (300, "dirty"),
            (499, "dirty"),
            (500, "very dirty"),
            (999, "very dirty"),
        ],
    )
    def test_label_thresholds(self, g_kwh, expected):
        assert carbon_label(g_kwh) == expected


class TestBuildRecommendationText:
    def _window(self, hour_local: str, rate: float, carbon: float, score: float) -> Window:
        return Window(
            hour_utc=hour_local,
            hour_local=hour_local,
            rate_usd_kwh=rate,
            carbon_g_kwh=carbon,
            solar_kw=0.0,
            net_cost_usd=round(rate * 1.5, 4),
            carbon_kg=round(carbon * 1.5 / 1000, 4),
            score=score,
        )

    def test_now_is_best(self):
        w = self._window("2026-01-01T10:00:00", 0.07, 80.0, 0.0)
        text = build_recommendation_text("dishwasher", w, w, [w])
        assert "now" in text.lower()
        assert "dishwasher" in text.lower()

    def test_future_best_mentions_time(self):
        current = self._window("2026-01-01T10:00:00", 0.17, 300.0, 0.9)
        best = self._window("2026-01-01T23:00:00", 0.07, 80.0, 0.0)
        text = build_recommendation_text("dishwasher", best, current, [best, current])
        assert "dishwasher" in text.lower()
        # Should mention the best time
        assert "11 pm" in text.lower()

    def test_cost_saving_shown_when_significant(self):
        current = self._window("2026-01-01T18:00:00", 0.20, 300.0, 0.9)
        best = self._window("2026-01-01T02:00:00", 0.07, 200.0, 0.0)
        text = build_recommendation_text("washer", best, current, [best])
        assert "cent" in text.lower()

    def test_no_cost_saving_when_trivial(self):
        current = self._window("2026-01-01T10:00:00", 0.10, 200.0, 0.5)
        best = self._window("2026-01-01T11:00:00", 0.099, 200.0, 0.0)
        text = build_recommendation_text("dishwasher", best, current, [best])
        assert "cent" not in text.lower()
