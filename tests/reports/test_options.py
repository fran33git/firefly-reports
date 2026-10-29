"""Period, GlobalFilters and ReportOptions: validation and fiscal-year arithmetic."""

import dataclasses
from datetime import date

import pytest

from firefly_reports.errors import ConfigurationError, FireflyReportsError
from firefly_reports.ledger.errors import LedgerError
from firefly_reports.reports.options import GlobalFilters, Period, ReportOptions


def test_for_year_defaults_to_the_calendar_year():
    p = Period.for_year(2025)
    assert (p.start, p.end, p.year_mode) == (date(2025, 1, 1), date(2025, 12, 31), True)


def test_for_year_with_a_fiscal_start():
    p = Period.for_year(2025, "04-01")
    assert (p.start, p.end) == (date(2025, 4, 1), date(2026, 3, 31))


def test_for_year_leap_day_fiscal_start_ends_on_feb_28():
    p = Period.for_year(2024, "02-29")
    assert (p.start, p.end) == (date(2024, 2, 29), date(2025, 2, 28))


@pytest.mark.parametrize(
    ("year", "fiscal"),
    [(2025, "02-29"), (1899, "01-01"), (2101, "01-01"), ("abc", "01-01"), (2025, "13-40")],
)
def test_for_year_rejects_invalid_input(year, fiscal):
    with pytest.raises(ConfigurationError):
        Period.for_year(year, fiscal)


def test_between_rejects_a_reversed_range():
    with pytest.raises(ConfigurationError):
        Period.between(date(2025, 1, 1), date(2024, 1, 1))
    p = Period.between(date(2025, 1, 1), date(2025, 6, 30))
    assert p.year_mode is False


def test_previous_period_is_one_year_earlier():
    assert Period.for_year(2024).previous == Period.for_year(2023)
    leap = Period.between(date(2024, 2, 29), date(2024, 2, 29))
    assert leap.previous.start == date(2023, 2, 28) == leap.previous.end


def test_tag_names_the_period():
    assert Period.for_year(2025).tag == "2025-01-01__2025-12-31"


def test_configuration_error_is_translated_and_in_the_hierarchy():
    err = ConfigurationError("errors.start_after_end", start="2025-01-01", end="2024-01-01")
    assert isinstance(err, FireflyReportsError)
    assert "2025-01-01" in str(err) and "errors." not in str(err)
    assert issubclass(LedgerError, FireflyReportsError)


def test_global_filters_activity_and_immutability():
    assert not GlobalFilters().is_active()
    assert GlobalFilters(accounts_include=("1",)).is_active()
    assert GlobalFilters(show_transfers=False).is_active()
    assert GlobalFilters(reconciled_only=True).is_active()
    with pytest.raises(dataclasses.FrozenInstanceError):
        GlobalFilters().show_transfers = False  # type: ignore[misc]


def test_report_options_defaults():
    o = ReportOptions()
    assert (o.currency, o.lang, o.legacy, o.historical_years) == ("€", "en", False, 3)
    assert o.pdf and o.excel and not o.filters.is_active()
