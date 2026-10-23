"""Builder of the category_ledger report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d


def build_category_ledger(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return transactions grouped and totaled by category (alphabetical)."""
    by_category: dict = defaultdict(list)

    for tx in transactions:
        tx_type = tx.get("type", "")
        if tx_type not in ("withdrawal", "deposit"):
            continue

        cat = tx.get("category_name") or i18n.t("common.uncategorized")
        amount = _d(tx.get("amount", 0))
        sign = -amount if tx_type == "withdrawal" else +amount

        by_category[cat].append(
            {
                "date": str(tx.get("date", ""))[:10],
                "description": tx.get("description", ""),
                "type": tx_type.capitalize(),
                "counterpart": (
                    tx.get("destination_name")
                    if tx_type == "withdrawal"
                    else tx.get("source_name", "")
                ),
                "amount": sign,
                "reconciled": tx.get("reconciled", False),
            }
        )

    sections = []
    for cat in sorted(by_category.keys()):
        rows = sorted(by_category[cat], key=lambda r: r["date"])
        sections.append(
            {
                "category_name": cat,
                "rows": rows,
                "total": sum(r["amount"] for r in rows),
                "count": len(rows),
            }
        )

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "sections": sections,
        "grand_total": sum(s["total"] for s in sections),
    }
