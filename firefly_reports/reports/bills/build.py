"""Builder of the bills report (pure: no I/O, Decimal money)."""

from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._labels import (
    frequency_label,
)
from firefly_reports.reports._money import _d


def build_bills_report(
    bills: list[dict[str, Any]],
    bill_txn: dict[str, list[dict[str, Any]]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return recurring bills and subscriptions with payment status."""
    bill_transactions = bill_txn
    rows = []
    total_expected = Decimal("0")
    total_paid = Decimal("0")

    for b in bills:
        attrs = b.get("attributes", b)
        bid = str(b.get("id", ""))
        active = attrs.get("active", True)

        amount_min = _d(attrs.get("amount_min", 0))
        amount_max = _d(attrs.get("amount_max", 0))
        # expected amount = midpoint of min/max range
        expected = ((amount_min + amount_max) / 2).quantize(Decimal("0.01"))

        # transactions matched to this bill in the period
        txs = bill_transactions.get(bid, [])
        paid_amount = sum(_d(tx.get("amount", 0)) for tx in txs)
        times_paid = len(txs)

        last_paid_date = ""
        if txs:
            dates = sorted(str(tx.get("date", ""))[:10] for tx in txs)
            last_paid_date = dates[-1]

        next_expected = attrs.get("next_expected_match") or "—"
        if next_expected and len(next_expected) > 10:
            next_expected = next_expected[:10]

        freq_raw = attrs.get("repeat_freq") or ""
        freq = frequency_label(freq_raw)

        rows.append(
            {
                "name": attrs.get("name", ""),
                "amount_min": amount_min,
                "amount_max": amount_max,
                "expected": expected,
                "frequency": freq,
                "next_expected": next_expected,
                "last_paid": last_paid_date,
                "paid_amount": paid_amount,
                "times_paid": times_paid,
                "active": active,
                "notes": (attrs.get("notes") or "").strip()[:60],
            }
        )
        if active:
            total_expected += expected
            total_paid += paid_amount

    rows.sort(key=lambda r: r["paid_amount"], reverse=True)

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "total_expected": total_expected,
        "total_paid": total_paid,
        "delta": total_paid - total_expected,
    }
