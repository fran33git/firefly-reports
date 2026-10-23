"""Builder of the transaction_register report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d


def build_transaction_register(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return chronological grouped transaction list with running balance."""
    from collections import OrderedDict

    grouped = OrderedDict()

    for idx, tx in enumerate(transactions):
        tx_type = tx.get("type", "")
        if tx_type == "opening balance":
            continue

        # Real API data always has group_id (set by _flatten_transactions);
        # fallbacks keep direct/mock use sane: never merge unrelated transactions.
        gid = (
            tx.get("group_id")
            or tx.get("id")
            or tx.get("transaction_journal_id")
            or f"__solo_{idx}"
        )
        if gid not in grouped:
            grouped[gid] = {
                "group_id": gid,
                "journal_id": "",
                "date": str(tx.get("date", ""))[:10],
                "description": tx.get("group_title") or tx.get("description", ""),
                "type": tx_type,
                "source": tx.get("source_name", ""),
                "destination": tx.get("destination_name", ""),
                "total": Decimal("0"),
                "total_abs": Decimal("0"),
                "currency": tx.get("currency_code", "EUR"),
                "reconciled": True,
                "has_attachments": False,
                "splits": [],
            }

        amount = _d(tx.get("amount", 0))
        sign = Decimal("0")

        if tx_type == "withdrawal":
            sign = -amount
        elif tx_type == "deposit":
            sign = +amount
        elif tx_type == "transfer":
            sign = -amount  # from the source account perspective

        grouped[gid]["total"] += sign
        grouped[gid]["total_abs"] += amount
        if not grouped[gid]["journal_id"]:
            grouped[gid]["journal_id"] = str(tx.get("id") or tx.get("transaction_journal_id") or "")
        grouped[gid]["reconciled"] = grouped[gid]["reconciled"] and tx.get("reconciled", False)
        grouped[gid]["has_attachments"] = grouped[gid]["has_attachments"] or tx.get(
            "has_attachments", False
        )
        grouped[gid]["splits"].append(
            {
                "id": tx.get("id") or tx.get("transaction_journal_id") or "",
                "description": tx.get("description", ""),
                "category": tx.get("category_name") or "",
                "budget": tx.get("budget_name") or "",
                "amount": sign,
                "amount_abs": amount,
                "foreign_amount": tx.get("foreign_amount"),
                "foreign_currency_code": tx.get("foreign_currency_code"),
                "notes": tx.get("notes") or "",
                "book_date": str(tx.get("book_date") or tx.get("date", ""))[:10],
                "external_id": tx.get("external_id") or "",
                "reconciled": tx.get("reconciled", False),
                "has_attachments": tx.get("has_attachments", False),
                "tags": tx.get("tags", []),
            }
        )

    rows = list(grouped.values())
    rows.sort(key=lambda r: r["date"])

    running = Decimal("0")
    for r in rows:
        running += r["total"]
        r["running_balance"] = running

    totals_by_type: dict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        totals_by_type[r["type"]] += r["total_abs"]

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "total_groups": len(rows),
        "total_transactions": sum(len(r["splits"]) for r in rows),
        "totals_by_type": dict(totals_by_type),
    }
