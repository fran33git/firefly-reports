"""Builder of the tagged report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d


def build_tagged_report(
    transactions: list[dict[str, Any]],
    tags: list[str],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
    match_all: bool = False,  # True = must have ALL tags, False = at least one
) -> dict[str, Any]:
    """Return transactions filtered by one or more tags."""
    tags_set = set(t.strip().lower() for t in tags)

    def _matches(tx: dict) -> bool:
        tx_tags = set(t.strip().lower() for t in (tx.get("tags") or []))
        if match_all:
            return tags_set.issubset(tx_tags)
        return bool(tags_set & tx_tags)

    income_by_cat: dict = defaultdict(Decimal)
    expense_by_cat: dict = defaultdict(Decimal)
    rows = []

    for tx in transactions:
        if not _matches(tx):
            continue
        tx_type = tx.get("type", "")
        if tx_type == "opening balance":
            continue

        amount = _d(tx.get("amount", 0))
        date_str = str(tx.get("date", ""))[:10]
        cat = tx.get("category_name") or i18n.t("common.uncategorized")
        tx_tags = tx.get("tags") or []

        if tx_type == "deposit":
            sign = +amount
            income_by_cat[cat] += amount
        elif tx_type == "withdrawal":
            sign = -amount
            expense_by_cat[cat] += amount
        elif tx_type == "transfer":
            sign = -amount
        else:
            sign = Decimal("0")

        rows.append(
            {
                "date": date_str,
                "description": tx.get("description", ""),
                "type": tx_type.capitalize(),
                "source": tx.get("source_name", ""),
                "destination": tx.get("destination_name", ""),
                "category": cat,
                "budget": tx.get("budget_name") or "",
                "tags": ", ".join(tx_tags),
                "amount": sign,
                "notes": tx.get("notes") or "",
            }
        )

    rows.sort(key=lambda r: r["date"])

    running = Decimal("0")
    for r in rows:
        running += r["amount"]
        r["running_balance"] = running

    total_in = sum(income_by_cat.values()) or Decimal("0")
    total_out = sum(expense_by_cat.values()) or Decimal("0")

    def _pct_rows(d: dict, total: Decimal) -> list:
        out = []
        for cat, amt in sorted(d.items(), key=lambda x: x[1], reverse=True):
            pct = (amt / total * 100).quantize(Decimal("0.1")) if total else Decimal("0")
            out.append({"category": cat, "amount": amt, "pct": pct})
        return out

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "tags": tags,
        "match_all": match_all,
        "rows": rows,
        "total_transactions": len(rows),
        "income_by_cat": _pct_rows(income_by_cat, total_in),
        "expense_by_cat": _pct_rows(expense_by_cat, total_out),
        "total_in": total_in,
        "total_out": total_out,
        "net": total_in - total_out,
    }
