"""Report registry types: what a report is, what it reads and what it needs to run."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from firefly_reports.reports.options import Period, ReportOptions

ReportData = Any  # Mapping[str, Any] for all reports, list[Mapping] for account_statements
SheetWriter = Callable[[Any, ReportData], None]


@dataclass(frozen=True)
class ReportContext:
    period: Period
    options: ReportOptions


@dataclass(frozen=True)
class SourceData:
    """Everything fetched from Firefly III for one run."""

    transactions: list[dict[str, Any]]
    transactions_prev: list[dict[str, Any]]
    accounts: list[dict[str, Any]]
    liabilities: list[dict[str, Any]]
    account_transactions: dict[str, list[dict[str, Any]]]
    liability_transactions: dict[str, list[dict[str, Any]]]
    budgets: list[dict[str, Any]]
    budget_limits: dict[str, list[dict[str, Any]]]
    bills: list[dict[str, Any]]
    bill_transactions: dict[str, list[dict[str, Any]]]
    piggy_banks: list[dict[str, Any]]
    about: dict[str, Any]
    about_user: dict[str, Any]
    links: list[dict[str, Any]]
    linked_extra: list[dict[str, Any]]  # deep-fetched with --fetch-links
    history: dict[int, dict[str, Any]]  # year -> totals and top categories


class Builder(Protocol):
    def __call__(
        self, src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData], /
    ) -> ReportData: ...


class PdfRenderer(Protocol):
    def __call__(self, data: ReportData, path: str, legacy: bool = False) -> None: ...


class FireflySource(Protocol):
    """The ``FireflyClient`` methods the pipeline calls (the demo client implements them too)."""

    def get_transactions(
        self, start: date | None = None, end: date | None = None, tx_type: str | None = None
    ) -> list[dict[str, Any]]: ...

    def get_asset_accounts(self) -> list[dict[str, Any]]: ...

    def get_liability_accounts(self) -> list[dict[str, Any]]: ...

    def get_account_transactions(
        self, account_id: Any, start: date, end: date
    ) -> list[dict[str, Any]]: ...

    def get_liability_transactions(
        self, account_id: Any, start: date, end: date
    ) -> list[dict[str, Any]]: ...

    def get_budgets(self) -> list[dict[str, Any]]: ...

    def get_budget_limits(self, budget_id: str, start: date, end: date) -> list[dict[str, Any]]: ...

    def get_bills(self) -> list[dict[str, Any]]: ...

    def get_bill_transactions(
        self, bill_id: str, start: date, end: date
    ) -> list[dict[str, Any]]: ...

    def get_piggy_banks(self) -> list[dict[str, Any]]: ...

    def get_about(self) -> dict[str, Any]: ...

    def get_about_user(self) -> dict[str, Any]: ...

    def get_annual_totals(self, year: int) -> dict[str, Any]: ...

    def get_top_categories_for_year(self, year: int, limit: int = 5) -> list[dict[str, Any]]: ...

    def get_transaction_links(self, resolve_types: bool = True) -> list[dict[str, Any]]: ...

    def fetch_link_details(self, journal_ids: list[str]) -> list[dict[str, Any]]: ...


def _always(ctx: ReportContext) -> bool:
    return True


def _always_pdf(ctx: ReportContext, data: ReportData) -> bool:
    return True


@dataclass(frozen=True)
class ReportSpec:
    """One report: how to build it, where it is rendered and when it applies."""

    key: str  # package name, e.g. "cash_flow"
    build: Builder  # adapter in the package: from_source()
    pdf: PdfRenderer | None
    filename: Callable[[ReportContext], str]  # PDF basename
    sheet: SheetWriter | None = None
    applies: Callable[[ReportContext], bool] = _always  # build at all?
    pdf_enabled: Callable[[ReportContext, ReportData], bool] = _always_pdf
    depends_on: tuple[str, ...] = ()
    view: bool = False  # True for the two dashboards (derived data, no builder of their own)
