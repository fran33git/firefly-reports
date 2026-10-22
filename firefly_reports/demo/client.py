"""Offline stand-in for ``FireflyClient`` serving the demo data (no network)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.demo import data

# year -> (income, expense, groceries): the demo history, years 2023-2025.
_DEFAULT_HISTORY: dict[int, tuple[str, str, str]] = {
    2023: ("45000.00", "38000.00", "4000.00"),
    2024: ("48000.00", "39000.00", "4200.00"),
    2025: ("52000.00", "41000.00", "4500.00"),
}


class DemoClient:
    """Implements the ``FireflyClient`` methods the report pipeline calls, from ``demo.data``."""

    def __init__(self, history: Mapping[int, tuple[str, str, str]] | None = None) -> None:
        data.ensure_ids(data.TXN_2025, "25-")
        data.ensure_ids(data.TXN_2024, "24-")
        self._history = dict(_DEFAULT_HISTORY if history is None else history)

    def get_transactions(
        self, start: date | None = None, end: date | None = None, tx_type: str | None = None
    ) -> list[dict[str, Any]]:
        lo = start.isoformat() if start else ""
        hi = end.isoformat() if end else "9999-12-31"
        return [
            tx
            for tx in (*data.TXN_2025, *data.TXN_2024)
            if lo <= str(tx["date"])[:10] <= hi and tx_type in (None, "all", tx["type"])
        ]

    def get_asset_accounts(self) -> list[dict[str, Any]]:
        return list(data.ACCOUNTS)

    def get_liability_accounts(self) -> list[dict[str, Any]]:
        return list(data.LIABILITIES)

    def get_account_transactions(
        self, account_id: int | str, start: date, end: date
    ) -> list[dict[str, Any]]:
        acc = str(account_id)
        return [
            tx
            for tx in self.get_transactions(start, end)
            if acc in (str(tx.get("source_id")), str(tx.get("destination_id")))
        ]

    def get_liability_transactions(
        self, account_id: int | str, start: date, end: date
    ) -> list[dict[str, Any]]:
        return []

    def get_budgets(self) -> list[dict[str, Any]]:
        return list(data.BUDGETS)

    def get_budget_limits(self, budget_id: str, start: date, end: date) -> list[dict[str, Any]]:
        return list(data.BUDGET_LIMITS.get(budget_id, []))

    def get_bills(self) -> list[dict[str, Any]]:
        return list(data.BILLS)

    def get_bill_transactions(self, bill_id: str, start: date, end: date) -> list[dict[str, Any]]:
        return list(data.BILL_TXN.get(bill_id, []))

    def get_piggy_banks(self) -> list[dict[str, Any]]:
        return list(data.PIGGY_BANKS)

    def get_about(self) -> dict[str, Any]:
        return dict(data.ABOUT)

    def get_about_user(self) -> dict[str, Any]:
        return dict(data.ABOUT_USER)

    def get_annual_totals(self, year: int) -> dict[str, Any]:
        row = self._history.get(year)
        if row is None:
            zero = Decimal("0")
            return {"income": zero, "expense": zero, "net": zero}
        income, expense = Decimal(row[0]), Decimal(row[1])
        return {"income": income, "expense": expense, "net": income - expense}

    def get_top_categories_for_year(self, year: int, limit: int = 5) -> list[dict[str, Any]]:
        row = self._history.get(year)
        if row is None:
            return []
        top = [
            {"category": "Rent", "amount": Decimal("12000.00")},
            {"category": "Groceries", "amount": Decimal(row[2])},
        ]
        return top[:limit]

    def get_transaction_links(self, resolve_types: bool = True) -> list[dict[str, Any]]:
        return list(data.TRANSACTION_LINKS)

    def fetch_link_details(self, journal_ids: list[str]) -> list[dict[str, Any]]:
        return []
