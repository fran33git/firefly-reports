"""Builder of the summary report (pure: no I/O, Decimal money)."""

from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d


def build_summary(
    transactions: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    liabilities: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    bills: list[dict[str, Any]],
    piggy_banks: list[dict[str, Any]],
    about: dict[str, Any],
    about_user: dict[str, Any],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return Firefly instance details, global counts and period statistics."""
    type_counts = {"deposit": 0, "withdrawal": 0, "transfer": 0}
    dates: list[str] = []
    account_names: set[str] = set()
    categories: set[str] = set()
    counterparts: set[str] = set()
    tags: set[str] = set()
    total_in = Decimal("0")
    total_out = Decimal("0")

    for tx in transactions:
        tx_type = tx.get("type", "")
        if tx_type == "opening balance":
            continue
        if tx_type in type_counts:
            type_counts[tx_type] += 1
        d = str(tx.get("date", ""))[:10]
        if d:
            dates.append(d)
        for name in (tx.get("source_name"), tx.get("destination_name")):
            if name:
                account_names.add(str(name))
        cat = tx.get("category_name")
        if cat:
            categories.add(str(cat))
        if tx_type == "withdrawal" and tx.get("destination_name"):
            counterparts.add(str(tx["destination_name"]))
        elif tx_type == "deposit" and tx.get("source_name"):
            counterparts.add(str(tx["source_name"]))
        tags.update(str(tg) for tg in (tx.get("tags") or []))
        amount = _d(tx.get("amount", 0))
        if tx_type == "deposit":
            total_in += amount
        elif tx_type == "withdrawal":
            total_out += amount

    days = (end - start).days + 1
    dates.sort()

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "instance": {
            "firefly_version": str(about.get("version", "")),
            "api_version": str(about.get("api_version", "")),
            "os": str(about.get("os", "")),
            "php_version": str(about.get("php_version", "")),
            "user_email": str(about_user.get("email", "")),
            "user_role": str(about_user.get("role", "")),
        },
        "counts": {
            "asset_accounts": len(accounts),
            "liabilities": len(liabilities),
            "budgets": len(budgets),
            "bills": len(bills),
            "piggy_banks": len(piggy_banks),
        },
        "period": {
            "tx_total": sum(type_counts.values()),
            "tx_deposits": type_counts["deposit"],
            "tx_withdrawals": type_counts["withdrawal"],
            "tx_transfers": type_counts["transfer"],
            "first_tx_date": dates[0] if dates else "",
            "last_tx_date": dates[-1] if dates else "",
            "accounts_used": len(account_names),
            "categories_used": len(categories),
            "payees_used": len(counterparts),
            "tags_used": len(tags),
            "avg_daily_income": _d(total_in / days),
            "avg_daily_expense": _d(total_out / days),
        },
    }
