"""Builder of the historical_growth report (pure: no I/O, Decimal money)."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


def build_historical_report(
    year_data: dict[int, dict[str, Any]],
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return year-over-year growth comparison across multiple years."""
    sorted_years = sorted(year_data.keys())

    rows = []
    for i, year in enumerate(sorted_years):
        data = year_data[year]
        income = _d(data.get("total_income", 0))
        expense = _d(data.get("total_expense", 0))
        net = _d(data.get("net_savings", 0))

        row = {
            "year": year,
            "income": income,
            "expense": expense,
            "net": net,
            "income_growth": Decimal("0"),
            "expense_growth": Decimal("0"),
            "net_growth": Decimal("0"),
        }

        if i > 0:
            prev_year = sorted_years[i - 1]
            prev_data = year_data[prev_year]

            prev_income = _d(prev_data.get("total_income", 0))
            prev_expense = _d(prev_data.get("total_expense", 0))
            prev_net = _d(prev_data.get("net_savings", 0))

            def calc_growth(current: Decimal, previous: Decimal) -> Decimal | None:
                if previous == 0:
                    return Decimal("0")
                return ((current - previous) / abs(previous) * 100).quantize(Decimal("0.1"))

            row["income_growth"] = calc_growth(income, prev_income)
            row["expense_growth"] = calc_growth(expense, prev_expense)
            row["net_growth"] = calc_growth(net, prev_net)

        rows.append(row)

    return {
        "owner": owner_name,
        "currency": currency_symbol,
        "rows": rows,
        "year_count": len(rows),
    }


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    o = ctx.options
    if not src.history:
        return None
    return build_historical_report(src.history, o.owner, o.currency)
