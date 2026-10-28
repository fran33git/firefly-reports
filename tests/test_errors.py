"""The error hierarchy: one base, translated lazily."""

from firefly_reports import i18n
from firefly_reports.errors import (
    ConfigurationError,
    FireflyAPIError,
    FireflyReportsError,
    ReportError,
)
from firefly_reports.ledger.errors import (
    AccountCollisionError,
    ConfigError,
    ConversionError,
    LedgerError,
)


def test_ledger_error_is_a_firefly_reports_error():
    for cls in (LedgerError, ConfigError, ConversionError, AccountCollisionError):
        assert issubclass(cls, FireflyReportsError)
    for cls in (ConfigurationError, FireflyAPIError, ReportError):
        assert issubclass(cls, FireflyReportsError)


def test_error_message_follows_active_language():
    err = ConfigurationError("errors.start_after_end", start="2025-01-01", end="2024-01-01")
    i18n.load("en")
    english = str(err)
    i18n.load("it")
    try:
        italian = str(err)
    finally:
        i18n.load("en")
    assert english != italian and "2025-01-01" in english and "2025-01-01" in italian


def test_error_keeps_key_and_params_and_degrades_gracefully():
    err = ReportError("errors.no_such_key", report="x")
    assert (err.message_key, err.params) == ("errors.no_such_key", {"report": "x"})
    assert str(err) == "errors.no_such_key"
    bad = ConfigurationError("errors.invalid_year")  # placeholder {year} missing
    assert "{year}" in str(bad)
