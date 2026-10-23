"""Builder of the kpi_scorecard report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d


def build_kpi_scorecard(
    transactions: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    liability_accounts: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return financial KPIs: burn rate, cash runway, savings rate, HHI."""

    total_in = Decimal("0")
    total_out = Decimal("0")
    income_by_client: dict = defaultdict(Decimal)
    by_month: dict = defaultdict(lambda: {"in": Decimal("0"), "out": Decimal("0")})

    for tx in transactions:
        t = tx.get("type", "")
        a = _d(tx.get("amount", 0))
        mk = str(tx.get("date", ""))[:7]
        if t == "deposit":
            total_in += a
            by_month[mk]["in"] += a
            client = tx.get("source_name") or "—"
            income_by_client[client] += a
        elif t == "withdrawal":
            total_out += a
            by_month[mk]["out"] += a

    n_months = max(len(by_month), 1)
    avg_monthly_in = (total_in / n_months).quantize(Decimal("0.01"))
    avg_monthly_out = (total_out / n_months).quantize(Decimal("0.01"))
    net_cash_flow = total_in - total_out

    savings_rate = (
        (net_cash_flow / total_in * 100).quantize(Decimal("0.1")) if total_in else Decimal("0")
    )
    burn_rate = avg_monthly_out

    liquid_assets = sum(
        _d(acc.get("attributes", acc).get("current_balance", 0))
        for acc in accounts
        if _d(acc.get("attributes", acc).get("current_balance", 0)) > 0
    )

    total_liab = sum(
        abs(_d(acc.get("attributes", acc).get("current_balance", 0))) for acc in liability_accounts
    )

    net_worth = liquid_assets - total_liab

    cash_runway = (
        (liquid_assets / burn_rate).quantize(Decimal("0.1")) if burn_rate else Decimal("0")
    )
    liquidity_ratio = (
        (liquid_assets / total_liab).quantize(Decimal("0.01"))
        if total_liab
        else None  # None = no liabilities
    )

    # Herfindahl-Hirschman Index for income concentration (0–10000)
    hhi = Decimal("0")
    if total_in > 0 and income_by_client:
        hhi = sum((amt / total_in * 100) ** 2 for amt in income_by_client.values()).quantize(
            Decimal("0.1")
        )

    top1_client = (
        max(income_by_client, key=lambda k: income_by_client[k]) if income_by_client else "—"
    )
    top1_pct = (
        (income_by_client[top1_client] / total_in * 100).quantize(Decimal("0.1"))
        if total_in and income_by_client
        else Decimal("0")
    )

    monthly_trend = []
    for mk in sorted(by_month):
        m_in = by_month[mk]["in"]
        m_out = by_month[mk]["out"]
        monthly_trend.append(
            {
                "month": mk,
                "income": m_in,
                "expense": m_out,
                "net": m_in - m_out,
            }
        )

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "total_in": total_in,
        "total_out": total_out,
        "net_cash_flow": net_cash_flow,
        "avg_monthly_in": avg_monthly_in,
        "avg_monthly_out": avg_monthly_out,
        "savings_rate": savings_rate,
        "burn_rate": burn_rate,
        "cash_runway": cash_runway,
        "liquid_assets": liquid_assets,
        "total_liab": total_liab,
        "net_worth": net_worth,
        "liquidity_ratio": liquidity_ratio,
        "hhi": hhi,
        "top1_client": top1_client,
        "top1_pct": top1_pct,
        "n_months": n_months,
        "monthly_trend": monthly_trend,
    }
