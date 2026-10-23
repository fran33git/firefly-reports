"""Global transaction filters (accounts, categories, transfers, reconciliation)."""

from typing import Any


def _asset_account_ids(tx: dict[str, Any]) -> list[str]:
    """Return the ID(s) of the asset-account side(s) of a transaction split."""
    src_type = tx.get("source_type", "")
    dst_type = tx.get("destination_type", "")
    src, dst = str(tx.get("source_id") or ""), str(tx.get("destination_id") or "")
    if src_type or dst_type:
        ids = []
        if "Asset" in str(src_type) and src:
            ids.append(src)
        if "Asset" in str(dst_type) and dst:
            ids.append(dst)
        return ids
    # Fallback by transaction type when type fields are missing (e.g. mock data)
    tx_type = tx.get("type", "")
    if tx_type == "withdrawal":
        return [src] if src else []
    if tx_type == "deposit":
        return [dst] if dst else []
    return [i for i in (src, dst) if i]  # transfer: both sides are asset accounts


def apply_global_filters(
    transactions: list[dict[str, Any]],
    *,
    accounts_include: list[str] | None = None,
    accounts_exclude: list[str] | None = None,
    categories_include: list[str] | None = None,
    categories_exclude: list[str] | None = None,
    show_transfers: bool = True,
    show_reconciled_only: bool = False,
) -> list[dict[str, Any]]:
    """Filter a flat transaction list according to the global report parameters.

    - accounts_*: matched against the asset-account side(s) of each transaction
      (IDs as strings). include wins over exclude for the kept set semantics:
      a transaction is kept if it touches an included account and does not
      touch an excluded one.
    - categories_*: case-insensitive match on category_name.
    - show_transfers=False drops transfer transactions entirely.
    - show_reconciled_only=True keeps only reconciled transactions.
    """
    inc_acc = {str(a) for a in accounts_include or []}
    exc_acc = {str(a) for a in accounts_exclude or []}
    inc_cat = {c.strip().lower() for c in categories_include or []}
    exc_cat = {c.strip().lower() for c in categories_exclude or []}

    out = []
    for tx in transactions:
        if not show_transfers and tx.get("type") == "transfer":
            continue
        if show_reconciled_only and not tx.get("reconciled", False):
            continue
        acc_ids = _asset_account_ids(tx)
        if inc_acc and not any(a in inc_acc for a in acc_ids):
            continue
        if exc_acc and any(a in exc_acc for a in acc_ids):
            continue
        cat = str(tx.get("category_name") or "").strip().lower()
        if inc_cat and cat not in inc_cat:
            continue
        if exc_cat and cat in exc_cat:
            continue
        out.append(tx)
    return out
