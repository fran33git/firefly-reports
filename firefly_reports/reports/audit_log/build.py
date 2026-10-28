"""Builder of the audit_log report (pure: no I/O, Decimal money)."""

from collections.abc import Mapping
from datetime import date
from typing import Any

from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


def build_audit_log(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return dense audit log with technical IDs and reconciliation status."""
    rows = []
    for tx in transactions:
        tx_type = tx.get("type", "")
        if tx_type == "opening balance":
            continue

        amount = _d(tx.get("amount", 0))
        # Audit log usually shows absolute amounts with type markers
        rows.append(
            {
                "id": tx.get("id") or tx.get("transaction_journal_id") or "",
                "external_id": tx.get("external_id") or "—",
                "group_id": tx.get("group_id") or "—",
                "date": str(tx.get("date", ""))[:10],
                "book_date": tx.get("book_date") or str(tx.get("date", ""))[:10],
                "description": tx.get("description", ""),
                "type": tx_type.capitalize(),
                "source": tx.get("source_name", ""),
                "destination": tx.get("destination_name", ""),
                "amount": amount,
                "currency": tx.get("currency_code", "EUR"),
                "category": tx.get("category_name") or "—",
                "budget": tx.get("budget_name") or "—",
                "reconciled": tx.get("reconciled", False),
                "reconciled_tag": "R" if tx.get("reconciled", False) else "U",
                "tags": ", ".join(tx.get("tags", [])),
                "has_attachments": tx.get("has_attachments", False),
            }
        )

    rows.sort(key=lambda r: (r["date"], r["id"]))

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "total_count": len(rows),
        "reconciled_count": sum(1 for r in rows if r["reconciled"]),
    }


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    p, o = ctx.period, ctx.options
    return build_audit_log(src.transactions, p.start, p.end, o.owner, o.currency)
