"""Builder of the yoy report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


def _aggregate_period(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate income and expenses by category from a transaction list."""
    income: dict = defaultdict(Decimal)
    expense: dict = defaultdict(Decimal)
    for tx in transactions:
        t = tx.get("type", "")
        a = _d(tx.get("amount", 0))
        cat = tx.get("category_name") or i18n.t("common.uncategorized")
        if t == "deposit":
            income[cat] += a
        elif t == "withdrawal":
            expense[cat] += a
    return {"income": income, "expense": expense}


def build_yoy_comparison(
    transactions_cur: list[dict[str, Any]],
    transactions_prev: list[dict[str, Any]],
    start_cur: date,
    end_cur: date,
    start_prev: date,
    end_prev: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return year-over-year comparison of income and expenses by category."""
    transactions_a, transactions_b = transactions_cur, transactions_prev
    start_a, end_a = start_cur, end_cur
    start_b, end_b = start_prev, end_prev
    agg_a = _aggregate_period(transactions_a)
    agg_b = _aggregate_period(transactions_b)

    all_cats_income = set(agg_a["income"]) | set(agg_b["income"])
    all_cats_expense = set(agg_a["expense"]) | set(agg_b["expense"])

    def _rows(cats: set, d_a: dict, d_b: dict, tx_type: str) -> list:
        rows = []
        for cat in sorted(cats):
            va = d_a.get(cat, Decimal("0"))
            vb = d_b.get(cat, Decimal("0"))
            delta = va - vb
            delta_pct = (delta / vb * 100).quantize(Decimal("0.1")) if vb else Decimal("0")
            rows.append(
                {
                    "category": cat,
                    "type": tx_type,
                    "amount_a": va,
                    "amount_b": vb,
                    "delta": delta,
                    "delta_pct": delta_pct,
                }
            )
        return sorted(rows, key=lambda r: r["amount_a"], reverse=True)

    income_rows = _rows(all_cats_income, agg_a["income"], agg_b["income"], "income")
    expense_rows = _rows(all_cats_expense, agg_a["expense"], agg_b["expense"], "expense")

    total_in_a = sum(agg_a["income"].values()) or Decimal("0")
    total_in_b = sum(agg_b["income"].values()) or Decimal("0")
    total_out_a = sum(agg_a["expense"].values()) or Decimal("0")
    total_out_b = sum(agg_b["expense"].values()) or Decimal("0")

    def _delta_pct(a: Decimal, b: Decimal) -> Decimal:
        if b:
            return ((a - b) / b * 100).quantize(Decimal("0.1"))
        return Decimal("0")

    return {
        "owner": owner_name,
        "currency": currency_symbol,
        "period_a": {
            "start": start_a,
            "end": end_a,
            "label": f"{start_a.year}"
            if start_a.year == end_a.year
            else f"{start_a.strftime('%d/%m/%y')}–{end_a.strftime('%d/%m/%y')}",
        },
        "period_b": {
            "start": start_b,
            "end": end_b,
            "label": f"{start_b.year}"
            if start_b.year == end_b.year
            else f"{start_b.strftime('%d/%m/%y')}–{end_b.strftime('%d/%m/%y')}",
        },
        "income_rows": income_rows,
        "expense_rows": expense_rows,
        "total_in_a": total_in_a,
        "total_in_b": total_in_b,
        "total_out_a": total_out_a,
        "total_out_b": total_out_b,
        "net_a": total_in_a - total_out_a,
        "net_b": total_in_b - total_out_b,
        "delta_in_pct": _delta_pct(total_in_a, total_in_b),
        "delta_out_pct": _delta_pct(total_out_a, total_out_b),
    }


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    p, o = ctx.period, ctx.options
    return build_yoy_comparison(
        src.transactions,
        src.transactions_prev,
        p.start,
        p.end,
        p.previous.start,
        p.previous.end,
        o.owner,
        o.currency,
    )
