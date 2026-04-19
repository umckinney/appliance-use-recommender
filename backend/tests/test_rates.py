"""Tests for backend.engine.rates — TOU rate resolution for Seattle City Light."""

import zoneinfo
from datetime import datetime

import pytest

from backend.engine.rates import get_24h_schedule, get_rate, list_utilities, load_utility

PT = zoneinfo.ZoneInfo("America/Los_Angeles")


def dt(day: str, hour: int) -> datetime:
    """Helper: local Pacific datetime for a given day string and hour."""
    return datetime.fromisoformat(f"2026-{day}T{hour:02d}:00:00").replace(tzinfo=PT)


class TestLoadUtility:
    def test_loads_seattle_city_light(self):
        cfg = load_utility("seattle_city_light")
        assert cfg["utility_id"] == "seattle_city_light"
        assert "rates" in cfg
        assert "schedules" in cfg

    def test_unknown_utility_raises(self):
        with pytest.raises(ValueError, match="Unknown utility"):
            load_utility("nonexistent_utility_xyz")

    def test_cached_on_second_call(self):
        cfg1 = load_utility("seattle_city_light")
        cfg2 = load_utility("seattle_city_light")
        assert cfg1 is cfg2  # same object from cache


class TestListUtilities:
    def test_returns_list_with_seattle(self):
        utils = list_utilities()
        ids = [u["utility_id"] for u in utils]
        assert "seattle_city_light" in ids

    def test_excludes_template(self):
        utils = list_utilities()
        names = [u["utility_id"] for u in utils]
        assert "TEMPLATE" not in names


class TestGetRate:
    """Seattle City Light TOU schedule:
    Peak:     17:00–21:00  Mon–Sat  (not Sun/holidays)
    Mid-peak: 06:00–17:00 and 21:00–24:00  Mon–Sat; all day Sun
    Off-peak: 00:00–06:00  Mon–Sat
    """

    # --- Weekday tests ---
    def test_weekday_offpeak_midnight(self):
        # Monday 01-05 is a weekday
        rate, period = get_rate("seattle_city_light", dt("01-05", 2))
        assert period == "off_peak"

    def test_weekday_midpeak_morning(self):
        rate, period = get_rate("seattle_city_light", dt("01-05", 10))
        assert period == "mid_peak"

    def test_weekday_peak_evening(self):
        rate, period = get_rate("seattle_city_light", dt("01-05", 18))
        assert period == "peak"

    def test_weekday_peak_boundary_start(self):
        rate, period = get_rate("seattle_city_light", dt("01-05", 17))
        assert period == "peak"

    def test_weekday_midpeak_after_peak(self):
        rate, period = get_rate("seattle_city_light", dt("01-05", 21))
        assert period == "mid_peak"

    # --- Weekend tests ---
    def test_sunday_is_not_peak(self):
        # 2026-01-04 is a Sunday
        rate, period = get_rate("seattle_city_light", dt("01-04", 18))
        assert period != "peak"

    def test_saturday_peak(self):
        # 2026-01-03 is a Saturday
        rate, period = get_rate("seattle_city_light", dt("01-03", 18))
        assert period == "peak"

    # --- Rate values ---
    def test_peak_rate_is_highest(self):
        cfg = load_utility("seattle_city_light")
        rates = cfg["rates"]
        assert rates["peak"] > rates["mid_peak"] > rates["off_peak"]

    def test_off_peak_rate_value(self):
        rate, _ = get_rate("seattle_city_light", dt("01-05", 3))
        assert rate == pytest.approx(0.0767, abs=0.001)


class TestGet24hSchedule:
    def test_returns_48_entries(self):
        schedule = get_24h_schedule("seattle_city_light", dt("01-05", 0))
        assert len(schedule) == 48

    def test_each_entry_has_required_keys(self):
        schedule = get_24h_schedule("seattle_city_light", dt("01-05", 0))
        for entry in schedule:
            assert "hour_local" in entry
            assert "rate_usd_kwh" in entry
            assert "rate_period" in entry

    def test_rates_are_positive(self):
        schedule = get_24h_schedule("seattle_city_light", dt("01-05", 0))
        for entry in schedule:
            assert entry["rate_usd_kwh"] > 0
