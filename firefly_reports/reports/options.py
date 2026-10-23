"""Report period and options: immutable values shared by the CLI and the library facade."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from firefly_reports.errors import ConfigurationError


def _one_year_earlier(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - 1, day=28)


@dataclass(frozen=True)
class Period:
    """A reporting period; ``year_mode`` unlocks the year-only reports."""

    start: date
    end: date
    year_mode: bool

    @classmethod
    def for_year(cls, year: int, fiscal_year_start: str = "01-01") -> Period:
        """The (fiscal) year starting on *fiscal_year_start* (``MM-DD``) of *year*."""
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            raise ConfigurationError("errors.invalid_year", year=year) from None
        if not 1900 <= year_int <= 2100:
            raise ConfigurationError("errors.year_out_of_range", year=year)
        try:
            # Parse against a leap year so 02-29 is accepted and no year-less parsing
            # deprecation warning is raised (CPython #70647).
            fy = datetime.strptime(f"2000-{fiscal_year_start}", "%Y-%m-%d").date()
        except ValueError:
            raise ConfigurationError(
                "errors.invalid_fiscal_start", value=fiscal_year_start
            ) from None
        try:
            start = date(year_int, fy.month, fy.day)
        except ValueError:
            raise ConfigurationError(
                "errors.fiscal_start_not_leap", value=fiscal_year_start, year=year_int
            ) from None
        try:
            fy_next = date(year_int + 1, fy.month, fy.day)
        except ValueError:
            # 02-29 anniversary in a non-leap following year: the fiscal year ends on 02-28.
            fy_next = date(year_int + 1, 3, 1)
        return cls(start, fy_next - timedelta(days=1), True)

    @classmethod
    def between(cls, start: date, end: date) -> Period:
        """An arbitrary range (year-only reports are skipped)."""
        if start > end:
            raise ConfigurationError("errors.start_after_end", start=start, end=end)
        return cls(start, end, False)

    @property
    def previous(self) -> Period:
        """The same span one year earlier (Feb 29 becomes Feb 28)."""
        return Period(_one_year_earlier(self.start), _one_year_earlier(self.end), self.year_mode)

    @property
    def tag(self) -> str:
        return f"{self.start}__{self.end}"


@dataclass(frozen=True)
class GlobalFilters:
    accounts_include: tuple[str, ...] = ()
    accounts_exclude: tuple[str, ...] = ()
    categories_include: tuple[str, ...] = ()
    categories_exclude: tuple[str, ...] = ()
    show_transfers: bool = True
    reconciled_only: bool = False

    def is_active(self) -> bool:
        return bool(
            self.accounts_include
            or self.accounts_exclude
            or self.categories_include
            or self.categories_exclude
            or not self.show_transfers
            or self.reconciled_only
        )


@dataclass(frozen=True)
class ReportOptions:
    owner: str = ""
    currency: str = "€"
    lang: str = "en"
    legacy: bool = False
    tags: tuple[str, ...] = ()
    all_tags: bool = False
    fetch_links: bool = False
    historical_years: int = 3
    deductible_keywords: tuple[str, ...] = ()
    filters: GlobalFilters = field(default_factory=GlobalFilters)
    pdf: bool = True
    excel: bool = True
