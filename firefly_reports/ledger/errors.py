"""Translatable exceptions for the ledger export."""

from __future__ import annotations

from firefly_reports.errors import FireflyReportsError


class LedgerError(FireflyReportsError):
    """Base of the ledger export errors (translation key plus parameters)."""


class ConfigError(LedgerError):
    """Invalid or unreadable mapping file."""


class ConversionError(LedgerError):
    """A Firefly split could not be converted into a ledger transaction."""


class AccountCollisionError(LedgerError):
    """Different Firefly accounts normalise to the same ledger account."""
