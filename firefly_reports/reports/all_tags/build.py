"""Builder of the all_tags report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d


def build_all_tags_report(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return all transactions grouped by their tags (alphabetical)."""
    by_tag: dict = defaultdict(lambda: {"rows": [], "total": Decimal("0")})

    for tx in transactions:
        tx_type = tx.get("type", "")
        if tx_type not in ("withdrawal", "deposit"):
            continue

        tags = tx.get("tags", [])
        if not tags:
            continue

        amount = _d(tx.get("amount", 0))
        sign = -amount if tx_type == "withdrawal" else +amount
        date_str = str(tx.get("date", ""))[:10]

        for tag in tags:
            by_tag[tag]["rows"].append(
                {
                    "date": date_str,
                    "description": tx.get("description", ""),
                    "category": tx.get("category_name") or "",
                    "amount": sign,
                }
            )
            by_tag[tag]["total"] += sign

    # Sort rows within each tag by date
    for tag_name in by_tag:
        by_tag[tag_name]["rows"].sort(key=lambda r: r["date"])

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "tags": dict(by_tag),
    }
