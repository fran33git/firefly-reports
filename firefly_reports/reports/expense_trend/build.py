"""Builder of the expense_trend report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d


def build_expense_trend(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return a category x month expense matrix."""

    months = set()
    cat_month: dict = defaultdict(lambda: defaultdict(Decimal))
    income_month: dict = defaultdict(Decimal)

    for tx in transactions:
        tx_type = tx.get("type", "")
        amount = _d(tx.get("amount", 0))
        mk = str(tx.get("date", ""))[:7]
        cat = tx.get("category_name") or i18n.t("common.uncategorized")

        if not mk:
            continue
        months.add(mk)

        if tx_type == "withdrawal":
            cat_month[cat][mk] += amount
        elif tx_type == "deposit":
            income_month[mk] += amount

    sorted_months = sorted(months)

    # rows: categories sorted by descending total
    cat_totals = {cat: sum(vals.values()) for cat, vals in cat_month.items()}
    sorted_cats = sorted(cat_totals, key=lambda c: cat_totals[c], reverse=True)

    rows = []
    for cat in sorted_cats:
        monthly_vals = [cat_month[cat].get(mk, Decimal("0")) for mk in sorted_months]
        total = sum(monthly_vals)
        rows.append(
            {
                "category": cat,
                "monthly": monthly_vals,
                "total": total,
            }
        )

    totals_by_month = [
        sum(cat_month[cat].get(mk, Decimal("0")) for cat in sorted_cats) for mk in sorted_months
    ]
    income_row = [income_month.get(mk, Decimal("0")) for mk in sorted_months]

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "months": sorted_months,
        "rows": rows,
        "totals_by_month": totals_by_month,
        "income_by_month": income_row,
        "grand_total": sum(totals_by_month),
    }
