"""Builder of the income_expense report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d


def build_income_expense(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return income vs expense summary with savings rate."""
    income_cats: dict = defaultdict(Decimal)
    expense_cats: dict = defaultdict(Decimal)
    budget_map: dict = defaultdict(Decimal)

    for tx in transactions:
        tx_type = tx.get("type", "")
        amount = _d(tx.get("amount", 0))
        cat = tx.get("category_name") or i18n.t("common.uncategorized")
        budget = tx.get("budget_name") or None

        if tx_type == "deposit":
            income_cats[cat] += amount
        elif tx_type == "withdrawal":
            expense_cats[cat] += amount
            if budget:
                budget_map[budget] += amount

    total_income = sum(income_cats.values()) or Decimal("0")
    total_expense = sum(expense_cats.values()) or Decimal("0")

    def with_pct(d: dict, total: Decimal) -> list:
        rows = []
        for cat, amt in sorted(d.items(), key=lambda x: x[1], reverse=True):
            pct = (amt / total * 100).quantize(Decimal("0.1")) if total else Decimal("0")
            rows.append({"category": cat, "amount": amt, "pct": pct})
        return rows

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "income_rows": with_pct(income_cats, total_income),
        "expense_rows": with_pct(expense_cats, total_expense),
        "total_income": total_income,
        "total_expense": total_expense,
        "net_savings": total_income - total_expense,
        "savings_rate": (
            ((total_income - total_expense) / total_income * 100).quantize(Decimal("0.1"))
            if total_income
            else Decimal("0")
        ),
        "budget_breakdown": sorted(
            [{"budget": k, "spent": v} for k, v in budget_map.items()],
            key=lambda x: x["spent"],
            reverse=True,
        ),
    }
