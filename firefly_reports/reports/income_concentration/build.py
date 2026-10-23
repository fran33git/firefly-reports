"""Builder of the income_concentration report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d


def build_income_concentration(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return income breakdown per client (revenue source account)."""
    client_data: dict = defaultdict(lambda: {"amount": Decimal("0"), "count": 0})
    monthly_by_client: dict = defaultdict(lambda: defaultdict(Decimal))

    for tx in transactions:
        if tx.get("type") != "deposit":
            continue
        a = _d(tx.get("amount", 0))
        client = tx.get("source_name") or i18n.t("common.unspecified")
        mk = str(tx.get("date", ""))[:7]
        client_data[client]["amount"] += a
        client_data[client]["count"] += 1
        monthly_by_client[client][mk] += a

    total_income = sum(d["amount"] for d in client_data.values()) or Decimal("0")

    rows = []
    for client, data in sorted(client_data.items(), key=lambda x: x[1]["amount"], reverse=True):
        pct = (
            (data["amount"] / total_income * 100).quantize(Decimal("0.1"))
            if total_income
            else Decimal("0")
        )
        rows.append(
            {
                "client": client,
                "amount": data["amount"],
                "pct": pct,
                "count": data["count"],
                "avg_per_tx": (data["amount"] / data["count"]).quantize(Decimal("0.01"))
                if data["count"]
                else Decimal("0"),
            }
        )

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "total_income": total_income,
        "client_count": len(rows),
    }
