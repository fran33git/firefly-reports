"""Builder of the cumulative_cashflow report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d


def build_cumulative_cashflow(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return monthly cumulative cash flow series."""
    by_month: dict = defaultdict(lambda: {"in": Decimal("0"), "out": Decimal("0")})

    for tx in transactions:
        t = tx.get("type", "")
        a = _d(tx.get("amount", 0))
        mk = str(tx.get("date", ""))[:7]
        if not mk:
            continue
        if t == "deposit":
            by_month[mk]["in"] += a
        elif t == "withdrawal":
            by_month[mk]["out"] += a

    months_dict: Mapping[str, Any] = i18n.current().section("months")

    cumulative = Decimal("0")
    months = []
    for mk in sorted(by_month):
        y, m = mk.split("-")
        m_in = by_month[mk]["in"]
        m_out = by_month[mk]["out"]
        net = m_in - m_out
        cumulative += net
        months.append(
            {
                "month": mk,
                "month_label": f"{months_dict.get(m, m)} {y}",
                "income": m_in,
                "expense": m_out,
                "net": net,
                "cumulative": cumulative,
            }
        )

    peak_month = max(months, key=lambda m: m["cumulative"]) if months else None
    low_month = min(months, key=lambda m: m["cumulative"]) if months else None

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "months": months,
        "final_cumulative": cumulative,
        "peak_month": peak_month,
        "low_month": low_month,
    }
