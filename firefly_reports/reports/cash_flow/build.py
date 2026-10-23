"""Builder of the cash_flow report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


def build_cash_flow(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
    accounts: list[dict[str, Any]] | None = None,
    liability_accounts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return income/expense breakdown by category with monthly totals.

    When ``accounts``/``liability_accounts`` are given, also computes the
    cash flow statement waterfall (operating / investing / financing, spec
    R-INT-03) with opening/closing cash. Closing cash is derived from the
    accounts' current_balance, so for past periods it is an estimate.
    """
    by_month: dict = defaultdict(lambda: {"in": Decimal("0"), "out": Decimal("0")})

    inflows_by_cat: dict = defaultdict(Decimal)
    outflows_by_cat: dict = defaultdict(Decimal)

    for tx in transactions:
        tx_type = tx.get("type", "")
        amount = _d(tx.get("amount", 0))
        month_key = str(tx.get("date", ""))[:7]  # YYYY-MM
        cat = tx.get("category_name") or i18n.t("common.uncategorized")

        if tx_type == "deposit":
            inflows_by_cat[cat] += amount
            by_month[month_key]["in"] += amount
        elif tx_type == "withdrawal":
            outflows_by_cat[cat] += amount
            by_month[month_key]["out"] += amount

    inflows = sorted(
        [{"category": k, "amount": v} for k, v in inflows_by_cat.items()],
        key=lambda x: x["amount"],
        reverse=True,
    )
    outflows = sorted(
        [{"category": k, "amount": v} for k, v in outflows_by_cat.items()],
        key=lambda x: x["amount"],
        reverse=True,
    )

    total_in = sum(i["amount"] for i in inflows) or Decimal("0")
    total_out = sum(o["amount"] for o in outflows) or Decimal("0")
    net = total_in - total_out

    for m in by_month:
        by_month[m]["net"] = by_month[m]["in"] - by_month[m]["out"]
    sorted_months = dict(sorted(by_month.items()))

    # ── Waterfall (R-INT-03): operating / investing / financing ──
    savings_ids = {
        str(a.get("id", ""))
        for a in accounts or []
        if (a.get("attributes", a).get("account_role") or "") == "savingsAsset"
    }
    liability_ids = {str(a.get("id", "")) for a in liability_accounts or []}
    waterfall: dict[str, dict[str, Decimal]] = {
        "operating": {"in": Decimal("0"), "out": Decimal("0")},
        "investing": {"in": Decimal("0"), "out": Decimal("0")},
        "financing": {"in": Decimal("0"), "out": Decimal("0")},
    }
    for tx in transactions:
        tx_type = tx.get("type", "")
        amount = _d(tx.get("amount", 0))
        src = str(tx.get("source_id") or "")
        dst = str(tx.get("destination_id") or "")
        if tx_type == "deposit":
            # money coming out of a liability account = new loan received
            section = "financing" if src in liability_ids else "operating"
            waterfall[section]["in"] += amount
        elif tx_type == "withdrawal":
            section = "financing" if dst in liability_ids else "operating"
            waterfall[section]["out"] += amount
        elif tx_type == "transfer":
            # Only classify transfers that move cash across "boundaries";
            # plain asset-to-asset transfers are cash-neutral and excluded.
            if dst in liability_ids:
                waterfall["financing"]["out"] += amount
            elif src in liability_ids:
                waterfall["financing"]["in"] += amount
            elif dst in savings_ids:
                waterfall["investing"]["out"] += amount
            elif src in savings_ids:
                waterfall["investing"]["in"] += amount

    for flows in waterfall.values():
        flows["net"] = flows["in"] - flows["out"]
    net_change = sum((s["net"] for s in waterfall.values()), Decimal("0"))

    closing_cash = None
    if accounts is not None:
        closing_cash = sum(
            (_d(a.get("attributes", a).get("current_balance", 0)) for a in accounts),
            Decimal("0"),
        )
    opening_cash = closing_cash - net_change if closing_cash is not None else None

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "inflows": inflows,
        "outflows": outflows,
        "total_in": total_in,
        "total_out": total_out,
        "net": net,
        "by_month": sorted_months,
        "waterfall": {
            **waterfall,
            "net_change": net_change,
            "opening_cash": opening_cash,
            "closing_cash": closing_cash,
        },
    }


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    p, o = ctx.period, ctx.options
    return build_cash_flow(
        src.transactions, p.start, p.end, o.owner, o.currency, src.accounts, src.liabilities
    )
