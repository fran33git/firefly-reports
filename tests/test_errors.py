"""The error hierarchy: one base, translated lazily."""

from firefly_reports import i18n
from firefly_reports.errors import (
    ConfigurationError,
    FireflyAPIError,
    FireflyReportsError,
    ReportError,
    UntrustedChainError,
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


def test_untrusted_chain_error_names_host_and_ca_in_both_languages():
    err = UntrustedChainError(
        host="firefly.example.org", label="Weak CA", reason="key compromised", spki="ab" * 32
    )
    assert isinstance(err, FireflyReportsError)
    assert (err.message_key, err.params["host"]) == (
        "errors.untrusted_chain",
        "firefly.example.org",
    )
    texts = {}
    for lang in ("en", "it"):
        i18n.load(lang)
        texts[lang] = str(err)
    i18n.load("en")
    assert texts["en"] != texts["it"]
    for text in texts.values():
        assert "firefly.example.org" in text and "Weak CA" in text
        assert "--trust-insecure-ssl" in text
        text.encode("cp1252")
