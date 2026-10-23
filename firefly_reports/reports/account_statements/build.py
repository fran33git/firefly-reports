"""Builder of the account_statements report (pure: no I/O, Decimal money)."""

from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._labels import (
    account_role_label,
)
from firefly_reports.reports._money import _d


def build_account_statements(
    accounts: list[dict[str, Any]],
    txn_by_account: dict[str, list[dict[str, Any]]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> list[dict[str, Any]]:
    """Return a statement dict for each account."""
    transactions_by_account = txn_by_account
    statements = []

    for acc in accounts:
        attrs = acc.get("attributes", acc)
        acc_id = str(acc.get("id", ""))
        txs = transactions_by_account.get(acc_id, [])

        rows = []
        for tx in txs:
            tx_type = tx.get("type", "")
            if tx_type == "opening balance":
                continue
            date_str = str(tx.get("date", ""))[:10]
            amount = _d(tx.get("amount", 0))

            # sign from the perspective of this account
            src_id = str(tx.get("source_id", ""))
            signed = -amount if src_id == acc_id else +amount

            rows.append(
                {
                    "id": tx.get("id") or tx.get("transaction_journal_id") or "",
                    "date": date_str,
                    "description": tx.get("description", ""),
                    "type": tx_type.capitalize(),
                    "counterpart": (
                        tx.get("destination_name")
                        if src_id == acc_id
                        else tx.get("source_name", "")
                    ),
                    "category": tx.get("category_name") or "",
                    "amount": signed,
                    "notes": tx.get("notes") or "",
                    "book_date": tx.get("book_date") or date_str,
                    "external_id": tx.get("external_id") or "",
                }
            )

        rows.sort(key=lambda r: r["date"])

        # opening balance = current balance minus net movement in the period
        current_bal = _d(attrs.get("current_balance", 0))
        period_net = sum(r["amount"] for r in rows)
        opening_bal = current_bal - period_net

        running = opening_bal
        for r in rows:
            running += r["amount"]
            r["running_balance"] = running

        closing_bal = running if rows else opening_bal

        statements.append(
            {
                "owner": owner_name,
                "period_start": start,
                "period_end": end,
                "currency": currency_symbol,
                "account_name": attrs.get("name", ""),
                "account_iban": attrs.get("iban") or "—",
                "account_role": account_role_label(
                    attrs.get("account_role") or "", i18n.t("common.account")
                ),
                "currency_code": attrs.get("currency_code", "EUR"),
                "opening_balance": opening_bal,
                "closing_balance": closing_bal,
                "total_in": sum(r["amount"] for r in rows if r["amount"] > 0) or Decimal("0"),
                "total_out": sum(r["amount"] for r in rows if r["amount"] < 0) or Decimal("0"),
                "rows": rows,
                "tx_count": len(rows),
                "updated_at": attrs.get("updated_at"),
            }
        )

    return statements
