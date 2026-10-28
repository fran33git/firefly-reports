"""Exceptions of firefly-reports: one translatable hierarchy for library and CLI."""

from __future__ import annotations

from firefly_reports.i18n import t


class FireflyReportsError(Exception):
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


class ConfigurationError(FireflyReportsError):
    """Invalid year, fiscal start, dates, URL, credentials or configuration."""


class FireflyAPIError(FireflyReportsError):
    """The Firefly III API could not be reached or answered with an error."""


class ReportError(FireflyReportsError):
    """A report could not be built (the report key is in the params)."""
