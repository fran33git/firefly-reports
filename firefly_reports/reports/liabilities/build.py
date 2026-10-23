"""Builder of the liabilities report (pure: no I/O, Decimal money)."""

from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._labels import (
    liability_type_label,
)
from firefly_reports.reports._money import _d


def build_liabilities_report(
    liability_accounts: list[dict[str, Any]],
    liab_txn: dict[str, list[dict[str, Any]]],
    as_of: date,
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return debt summary with balance and period movement per liability."""
    transactions_by_account = liab_txn
    as_of_date = as_of
    rows = []
    total_debt = Decimal("0")
    total_payments = Decimal("0")

    for acc in liability_accounts:
        attrs = acc.get("attributes", acc)
        acc_id = str(acc.get("id", ""))
        bal = _d(attrs.get("current_balance", 0))
        # Firefly liabilities may have positive or negative balance depending on setup;
        # normalise so debt amount is always positive
        debt_amount = abs(bal)

        liab_type = attrs.get("liability_type") or attrs.get("account_role") or ""
        type_label = liability_type_label(liab_type)
        interest = _d(attrs.get("interest", 0))

        txs = transactions_by_account.get(acc_id, [])
        period_payments = sum(
            _d(tx.get("amount", 0)) for tx in txs if tx.get("type") in ("withdrawal", "deposit")
        )

        rows.append(
            {
                "name": attrs.get("name", ""),
                "type": type_label,
                "balance": bal,
                "debt_amount": debt_amount,
                "interest_rate": interest,
                "currency_code": attrs.get("currency_code", "EUR"),
                "period_payments": period_payments,
                "opening_date": (
                    attrs.get("opening_balance_date") or attrs.get("created_at") or ""
                )[:10],
                "notes": (attrs.get("notes") or "").strip()[:60],
            }
        )
        total_debt += debt_amount
        total_payments += period_payments

    rows.sort(key=lambda r: r["debt_amount"], reverse=True)

    return {
        "owner": owner_name,
        "as_of_date": as_of_date,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "total_debt": total_debt,
        "total_payments": total_payments,
        "liability_count": len(rows),
    }
