"""Calendar-complete monthly NetCDF aggregation tests."""

import numpy as np

from geoint.netcdf_computation_tools import _aggregate_monthly_values, _monthly_slices


def _covered_indices(slices: list[slice]) -> list[int]:
    return [index for month in slices for index in range(month.start, month.stop)]


def test_given_gregorian_year_when_partitioning_then_final_days_are_in_december() -> (
    None
):
    slices = _monthly_slices(365, 2026)

    assert len(slices) == 12
    assert slices[0] == slice(0, 31)
    assert slices[-1] == slice(334, 365)
    assert _covered_indices(slices) == list(range(365))


def test_given_leap_or_360_day_calendar_when_partitioning_then_all_days_are_used() -> (
    None
):
    leap = _monthly_slices(366, 2026)
    model = _monthly_slices(360, 2026)

    assert leap[1] == slice(31, 60)
    assert leap[-1].stop == 366
    assert all(month.stop - month.start == 30 for month in model)
    assert _covered_indices(model) == list(range(360))


def test_given_unknown_calendar_length_when_partitioning_then_no_sample_is_dropped() -> (
    None
):
    slices = _monthly_slices(367, 2026)

    assert _covered_indices(slices) == list(range(367))


def test_given_precipitation_only_in_final_days_when_aggregating_then_december_is_wettest() -> (
    None
):
    values = np.zeros(365)
    values[-5:] = 31.0

    periods = _aggregate_monthly_values(values, 2026, lambda value: value, "mm/day")

    assert len(periods) == 12
    assert periods[0]["mean"] == 0.0
    assert periods[-1]["period"] == "Dec"
    assert periods[-1]["mean"] == 5.0
    assert max(periods, key=lambda period: period["mean"])["period"] == "Dec"
