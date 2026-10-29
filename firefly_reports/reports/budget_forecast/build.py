"""Builder of the budget_forecast report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import clock
from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


def build_performance_forecast(
    budgets: list[dict[str, Any]],
    budget_limits: dict[str, list[dict[str, Any]]],
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Project month-end spending based on current velocity."""

    actual_by_budget: dict = defaultdict(Decimal)

    now = clock.today()
    total_days = (end - start).days + 1
    if now < start:
        days_elapsed = 0
    elif now > end:
        days_elapsed = total_days
    else:
        days_elapsed = (now - start).days + 1

    for tx in transactions:
        if tx.get("type") != "withdrawal":
            continue
        amount = _d(tx.get("amount", 0))
        budget = tx.get("budget_name") or tx.get("budget_id") or None
        if budget:
            actual_by_budget[str(budget)] += amount

    rows = []
    for b in budgets:
        attrs = b.get("attributes", b)
        bid = str(b.get("id", ""))
        bname = attrs.get("name", "")

        limits_list = budget_limits.get(bid, [])
        if limits_list:
            limit_amount = sum(
                _d(lim.get("attributes", lim).get("amount", 0)) for lim in limits_list
            )
        else:
            limit_amount = _d(attrs.get("auto_budget_amount", 0))

        actual = actual_by_budget.get(bname, Decimal("0"))

        # Forecast: average daily spend * total days
        daily_avg = (actual / days_elapsed) if days_elapsed > 0 else Decimal("0")
        forecast = (daily_avg * total_days).quantize(Decimal("0.01"))
        variance = limit_amount - forecast

        status = "on_track"
        if limit_amount > 0:
            if forecast > limit_amount * Decimal("1.1"):
                status = "critical"
            elif forecast > limit_amount:
                status = "warning"
            elif forecast < limit_amount * Decimal("0.8"):
                status = "under"

        rows.append(
            {
                "budget_name": bname,
                "limit": limit_amount,
                "actual": actual,
                "daily_avg": daily_avg.quantize(Decimal("0.01")),
                "forecast": forecast,
                "variance": variance,
                "status": status,
            }
        )

    rows.sort(key=lambda r: r["forecast"], reverse=True)

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "days_elapsed": days_elapsed,
        "total_days": total_days,
        "total_limit": sum(r["limit"] for r in rows),
        "total_actual": sum(r["actual"] for r in rows),
        "total_forecast": sum(r["forecast"] for r in rows),
    }


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    p, o = ctx.period, ctx.options
    return build_performance_forecast(
        src.budgets, src.budget_limits, src.transactions, p.start, p.end, o.owner, o.currency
    )
