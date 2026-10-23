"""Builder of the journal report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d


def build_journal(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Chronological journal with protocol numbers and Debit/Credit columns.

    Classic libro giornale format (R-ITA-06): each transaction produces TWO
    lines sharing the same protocol number — the Debit line (destination
    account, amount in the Debit column) and the Credit line (source account,
    amount in the Credit column). Mapping: withdrawal → expense Debited,
    deposit → asset Debited, transfer → destination asset Debited.
    Protocol numbers are assigned at runtime, chronologically.
    Each row has either "debit" or "credit" set, never both (the other is None).
    """
    sorted_txns = sorted(
        (tx for tx in transactions if tx.get("type") != "opening balance"),
        key=lambda tx: (
            str(tx.get("date", "")),
            str(tx.get("id") or tx.get("transaction_journal_id") or ""),
        ),
    )

    rows: list[dict[str, Any]] = []
    daily: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"debit": Decimal("0"), "credit": Decimal("0")}
    )
    for n, tx in enumerate(sorted_txns, 1):
        amount = abs(_d(tx.get("amount", 0)))
        day = str(tx.get("date", ""))[:10]
        rows.append(
            {
                "n": n,
                "date": day,
                "description": tx.get("description", ""),
                "account": tx.get("destination_name", ""),
                "debit": amount,
                "credit": None,
                "notes": (tx.get("notes") or "").strip(),
            }
        )
        rows.append(
            {
                "n": n,
                "date": day,
                "description": "",
                "account": tx.get("source_name", ""),
                "debit": None,
                "credit": amount,
                "notes": "",
            }
        )
        daily[day]["debit"] += amount
        daily[day]["credit"] += amount

    daily_totals: list[dict[str, Any]] = [
        {"date": day, "debit": v["debit"], "credit": v["credit"]}
        for day, v in sorted(daily.items())
    ]

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "daily_totals": daily_totals,
        "total_debit": sum((d["debit"] for d in daily_totals), Decimal("0")),
        "total_credit": sum((d["credit"] for d in daily_totals), Decimal("0")),
        "count": len(sorted_txns),  # journal entries (protocols); rows are 2× entries
    }
