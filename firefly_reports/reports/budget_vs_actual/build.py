"""Builder of the budget_vs_actual report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import clock
from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


def build_budget_vs_actual(
    budgets: list[dict[str, Any]],
    budget_limits: dict[str, list[dict[str, Any]]],
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return budget planned vs actual spend per budget line."""

    actual_by_budget: dict = defaultdict(Decimal)
    unbudgeted = Decimal("0")

    # Calculate % of month elapsed
    now = clock.today()
    if now < start:
        elapsed_pct = Decimal("0")
    elif now > end:
        elapsed_pct = Decimal("100")
    else:
        total_days = (end - start).days + 1
        elapsed_days = (now - start).days + 1
        elapsed_pct = (Decimal(elapsed_days) / Decimal(total_days) * 100).quantize(Decimal("0.1"))

    for tx in transactions:
        if tx.get("type") != "withdrawal":
            continue
        amount = _d(tx.get("amount", 0))
        budget = tx.get("budget_name") or tx.get("budget_id") or None
        if budget:
            actual_by_budget[str(budget)] += amount
        else:
            unbudgeted += amount

    rows = []
    total_limit = Decimal("0")
    total_actual = Decimal("0")

    for b in budgets:
        attrs = b.get("attributes", b)
        bid = str(b.get("id", ""))
        bname = attrs.get("name", "")
        auto_budget = attrs.get("auto_budget_amount")

        # prefer the period budget_limit if present, fall back to auto_budget_amount
        limits_list = budget_limits.get(bid, [])
        if limits_list:
            # sum all limits for the period (may be split monthly)
            limit_amount = sum(
                _d(lim.get("attributes", lim).get("amount", 0)) for lim in limits_list
            )
        elif auto_budget:
            limit_amount = _d(auto_budget)
        else:
            limit_amount = Decimal("0")

        # transactions carry budget_name, not budget_id
        actual = actual_by_budget.get(bname, Decimal("0"))

        variance = limit_amount - actual
        variance_pct = (
            (variance / limit_amount * 100).quantize(Decimal("0.1"))
            if limit_amount
            else Decimal("0")
        )
        spent_pct = (
            (actual / limit_amount * 100).quantize(Decimal("0.1")) if limit_amount else Decimal("0")
        )

        if limit_amount == 0:
            status = "no_limit"
            pace_status = "N/A"
        else:
            if actual > limit_amount:
                status = "over"
            elif actual >= limit_amount * Decimal("0.9"):
                status = "warning"
            else:
                status = "under"

            if spent_pct > elapsed_pct + 10:
                pace_status = "AHEAD"
            elif spent_pct < elapsed_pct - 10:
                pace_status = "UNDER"
            else:
                pace_status = "ON TRACK"

        rows.append(
            {
                "budget_name": bname,
                "limit": limit_amount,
                "actual": actual,
                "variance": variance,
                "variance_pct": variance_pct,
                "spent_pct": spent_pct,
                "status": status,
                "pace_status": pace_status,
            }
        )
        total_limit += limit_amount
        total_actual += actual

    rows.sort(key=lambda r: r["actual"], reverse=True)

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "total_limit": total_limit,
        "total_actual": total_actual,
        "total_variance": total_limit - total_actual,
        "unbudgeted_spending": unbudgeted,
        "elapsed_pct": elapsed_pct,
    }


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    p, o = ctx.period, ctx.options
    return build_budget_vs_actual(
        src.budgets, src.budget_limits, src.transactions, p.start, p.end, o.owner, o.currency
    )
