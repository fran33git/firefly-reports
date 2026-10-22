"""Translatable exceptions for the ledger export."""

from __future__ import annotations

from firefly_reports.i18n import t


class LedgerError(Exception):
    """Base error: carries a translation key plus format parameters.

    The message is rendered lazily in ``__str__`` so it follows the language
    that is active when the error is shown, not when it was raised.
    """

    def __init__(self, message_key: str, /, **params: object) -> None:
        super().__init__(message_key)
        self.message_key = message_key
        self.params = params

    def __str__(self) -> str:
        template = t(self.message_key)
        try:
            return template.format(**self.params)
        except (KeyError, IndexError):
            return template


class ConfigError(LedgerError):
    """Invalid or unreadable mapping file."""


class ConversionError(LedgerError):
    """A Firefly split could not be converted into a ledger transaction."""


class AccountCollisionError(LedgerError):
    """Different Firefly accounts normalise to the same ledger account."""
