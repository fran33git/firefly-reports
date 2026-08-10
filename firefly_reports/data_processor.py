"""
Report data processor: aggregates raw API data into structures ready for PDF/Excel rendering.
"""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from firefly_reports import i18n


def _d(value: Any) -> Decimal:
    """Coerce a value to Decimal with 2 decimal places, returning 0.00 on failure."""
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


# ─────────────────────────────────────────────
# Global filters (spec sez. 5)
# ─────────────────────────────────────────────


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


# ─────────────────────────────────────────────
# Report 1 — Cash Flow Statement
# ─────────────────────────────────────────────


def build_cash_flow(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
    accounts: list[dict[str, Any]] | None = None,
    liability_accounts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return income/expense breakdown by category with monthly totals.

    When ``accounts``/``liability_accounts`` are given, also computes the
    cash flow statement waterfall (operating / investing / financing, spec
    R-INT-03) with opening/closing cash. Closing cash is derived from the
    accounts' current_balance, so for past periods it is an estimate.
    """
    by_month: dict = defaultdict(lambda: {"in": Decimal("0"), "out": Decimal("0")})

    inflows_by_cat: dict = defaultdict(Decimal)
    outflows_by_cat: dict = defaultdict(Decimal)

    for tx in transactions:
        tx_type = tx.get("type", "")
        amount = _d(tx.get("amount", 0))
        month_key = str(tx.get("date", ""))[:7]  # YYYY-MM
        cat = tx.get("category_name") or i18n.t("common.uncategorized")

        if tx_type == "deposit":
            inflows_by_cat[cat] += amount
            by_month[month_key]["in"] += amount
        elif tx_type == "withdrawal":
            outflows_by_cat[cat] += amount
            by_month[month_key]["out"] += amount

    inflows = sorted(
        [{"category": k, "amount": v} for k, v in inflows_by_cat.items()],
        key=lambda x: x["amount"],
        reverse=True,
    )
    outflows = sorted(
        [{"category": k, "amount": v} for k, v in outflows_by_cat.items()],
        key=lambda x: x["amount"],
        reverse=True,
    )

    total_in = sum(i["amount"] for i in inflows) or Decimal("0")
    total_out = sum(o["amount"] for o in outflows) or Decimal("0")
    net = total_in - total_out

    for m in by_month:
        by_month[m]["net"] = by_month[m]["in"] - by_month[m]["out"]
    sorted_months = dict(sorted(by_month.items()))

    # ── Waterfall (R-INT-03): operating / investing / financing ──
    savings_ids = {
        str(a.get("id", ""))
        for a in accounts or []
        if (a.get("attributes", a).get("account_role") or "") == "savingsAsset"
    }
    liability_ids = {str(a.get("id", "")) for a in liability_accounts or []}
    waterfall: dict[str, dict[str, Decimal]] = {
        "operating": {"in": Decimal("0"), "out": Decimal("0")},
        "investing": {"in": Decimal("0"), "out": Decimal("0")},
        "financing": {"in": Decimal("0"), "out": Decimal("0")},
    }
    for tx in transactions:
        tx_type = tx.get("type", "")
        amount = _d(tx.get("amount", 0))
        src = str(tx.get("source_id") or "")
        dst = str(tx.get("destination_id") or "")
        if tx_type == "deposit":
            # money coming out of a liability account = new loan received
            section = "financing" if src in liability_ids else "operating"
            waterfall[section]["in"] += amount
        elif tx_type == "withdrawal":
            section = "financing" if dst in liability_ids else "operating"
            waterfall[section]["out"] += amount
        elif tx_type == "transfer":
            # Only classify transfers that move cash across "boundaries";
            # plain asset-to-asset transfers are cash-neutral and excluded.
            if dst in liability_ids:
                waterfall["financing"]["out"] += amount
            elif src in liability_ids:
                waterfall["financing"]["in"] += amount
            elif dst in savings_ids:
                waterfall["investing"]["out"] += amount
            elif src in savings_ids:
                waterfall["investing"]["in"] += amount

    for flows in waterfall.values():
        flows["net"] = flows["in"] - flows["out"]
    net_change = sum((s["net"] for s in waterfall.values()), Decimal("0"))

    closing_cash = None
    if accounts is not None:
        closing_cash = sum(
            (_d(a.get("attributes", a).get("current_balance", 0)) for a in accounts),
            Decimal("0"),
        )
    opening_cash = closing_cash - net_change if closing_cash is not None else None

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "inflows": inflows,
        "outflows": outflows,
        "total_in": total_in,
        "total_out": total_out,
        "net": net,
        "by_month": sorted_months,
        "waterfall": {
            **waterfall,
            "net_change": net_change,
            "opening_cash": opening_cash,
            "closing_cash": closing_cash,
        },
    }


# ─────────────────────────────────────────────
# Report 2 — Income & Expense Summary
# ─────────────────────────────────────────────


def build_income_expense(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return income vs expense summary with savings rate."""
    income_cats: dict = defaultdict(Decimal)
    expense_cats: dict = defaultdict(Decimal)
    budget_map: dict = defaultdict(Decimal)

    for tx in transactions:
        tx_type = tx.get("type", "")
        amount = _d(tx.get("amount", 0))
        cat = tx.get("category_name") or i18n.t("common.uncategorized")
        budget = tx.get("budget_name") or None

        if tx_type == "deposit":
            income_cats[cat] += amount
        elif tx_type == "withdrawal":
            expense_cats[cat] += amount
            if budget:
                budget_map[budget] += amount

    total_income = sum(income_cats.values()) or Decimal("0")
    total_expense = sum(expense_cats.values()) or Decimal("0")

    def with_pct(d: dict, total: Decimal) -> list:
        rows = []
        for cat, amt in sorted(d.items(), key=lambda x: x[1], reverse=True):
            pct = (amt / total * 100).quantize(Decimal("0.1")) if total else Decimal("0")
            rows.append({"category": cat, "amount": amt, "pct": pct})
        return rows

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "income_rows": with_pct(income_cats, total_income),
        "expense_rows": with_pct(expense_cats, total_expense),
        "total_income": total_income,
        "total_expense": total_expense,
        "net_savings": total_income - total_expense,
        "savings_rate": (
            ((total_income - total_expense) / total_income * 100).quantize(Decimal("0.1"))
            if total_income
            else Decimal("0")
        ),
        "budget_breakdown": sorted(
            [{"budget": k, "spent": v} for k, v in budget_map.items()],
            key=lambda x: x["spent"],
            reverse=True,
        ),
    }


# ─────────────────────────────────────────────
# Report 3 — Transaction Register
# ─────────────────────────────────────────────


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


# ─────────────────────────────────────────────
# Report 4 — Asset & Net Worth Statement
# ─────────────────────────────────────────────

_ROLE_ORDER = (
    "defaultAsset",
    "savingsAsset",
    "sharedAsset",
    "ccAsset",
    "cashWalletAsset",
    "other",
)


def _account_role_label(role: str, default: str = "") -> str:
    """Translate a Firefly account role; unknown roles fall back to *default* or 'other'."""
    if not role:
        role = "other"
    if role in _ROLE_ORDER:
        return str(i18n.t(f"account_roles.{role}"))
    return default or i18n.t("account_roles.other")


def build_net_worth(
    accounts: list[dict[str, Any]],
    as_of: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return net worth grouped by account type."""
    as_of_date = as_of
    from collections import defaultdict

    groups: dict = defaultdict(list)

    for acc in accounts:
        attrs = acc.get("attributes", acc)  # supports both raw API items and flat dicts
        role = attrs.get("account_role") or ""
        label = _account_role_label(role)
        bal = _d(attrs.get("current_balance", 0))
        iban = attrs.get("iban") or ""
        # mask IBAN: show only last 4 characters
        iban_masked = ("*" * max(0, len(iban) - 4) + iban[-4:]) if iban else "—"

        groups[label].append(
            {
                "name": attrs.get("name", ""),
                "iban_masked": iban_masked,
                "balance": bal,
                "currency_code": attrs.get("currency_code", "EUR"),
                "notes": (attrs.get("notes") or "").strip()[:60],
                "active": attrs.get("active", True),
                "updated_at": attrs.get("updated_at"),
            }
        )

    # canonical group order
    order = [_account_role_label(r) for r in _ROLE_ORDER]
    sorted_groups = []
    for lbl in order:
        if lbl in groups:
            accs = sorted(groups[lbl], key=lambda a: a["name"])
            subtotal = sum(a["balance"] for a in accs)
            sorted_groups.append({"role_label": lbl, "accounts": accs, "subtotal": subtotal})
    # append any groups not in the canonical mapping
    for lbl, accs in groups.items():
        if lbl not in order:
            subtotal = sum(a["balance"] for a in accs)
            sorted_groups.append({"role_label": lbl, "accounts": accs, "subtotal": subtotal})

    all_bals = [a["balance"] for g in sorted_groups for a in g["accounts"]]
    total_assets = sum(b for b in all_bals if b >= 0) or Decimal("0")
    total_liabilities = sum(b for b in all_bals if b < 0) or Decimal("0")
    net_worth = total_assets + total_liabilities

    return {
        "owner": owner_name,
        "as_of_date": as_of_date,
        "currency": currency_symbol,
        "groups": sorted_groups,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "net_worth": net_worth,
        "account_count": len(all_bals),
    }


# ─────────────────────────────────────────────
# Report 5 — Account Statement (per conto)
# ─────────────────────────────────────────────


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
                "account_role": _account_role_label(
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


# ─────────────────────────────────────────────
# Report 6 — Annual Tax Summary
# ─────────────────────────────────────────────


def build_tax_summary(
    transactions: list[dict[str, Any]],
    year: int,
    owner_name: str = "",
    currency_symbol: str = "EUR",
    professional_income_categories: list | None = None,
    deductible_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Return cash-basis tax summary: deductible expenses and taxable income."""
    from collections import defaultdict

    pro_cats = set(professional_income_categories or [])
    deductible_kws = [kw.lower() for kw in (deductible_keywords or [])]

    def _is_deductible_local(cat_name: str) -> bool:
        if not deductible_kws:
            return False
        cat_l = cat_name.lower()
        return any(kw in cat_l for kw in deductible_kws)

    income_by_cat: dict = defaultdict(Decimal)
    income_by_client: dict = defaultdict(Decimal)
    deductible_by_cat: dict = defaultdict(Decimal)
    nondeductible_by_cat: dict = defaultdict(Decimal)

    for tx in transactions:
        tx_type = tx.get("type", "")
        tx_year = int(str(tx.get("date", "0000"))[:4])
        if tx_year != year:
            continue
        amount = _d(tx.get("amount", 0))
        cat = tx.get("category_name") or i18n.t("common.uncategorized")

        if tx_type == "deposit":
            income_by_cat[cat] += amount
            client = tx.get("source_name") or "—"
            income_by_client[client] += amount

        elif tx_type == "withdrawal":
            if _is_deductible_local(cat) or cat in pro_cats:
                deductible_by_cat[cat] += amount
            else:
                nondeductible_by_cat[cat] += amount

    total_income = sum(income_by_cat.values()) or Decimal("0")
    total_deductible = sum(deductible_by_cat.values()) or Decimal("0")
    total_nonded = sum(nondeductible_by_cat.values()) or Decimal("0")
    taxable_estimate = total_income - total_deductible

    def _sorted_rows(d: dict) -> list:
        return sorted(
            [{"category": k, "amount": v} for k, v in d.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )

    return {
        "owner": owner_name,
        "year": year,
        "currency": currency_symbol,
        "income_by_cat": _sorted_rows(income_by_cat),
        "income_by_client": sorted(
            [{"client": k, "amount": v} for k, v in income_by_client.items()],
            key=lambda x: x["amount"],
            reverse=True,
        ),
        "deductible_rows": _sorted_rows(deductible_by_cat),
        "nondeductible_rows": _sorted_rows(nondeductible_by_cat),
        "total_income": total_income,
        "total_deductible": total_deductible,
        "total_nondeductible": total_nonded,
        "taxable_estimate": taxable_estimate,
    }


# ─────────────────────────────────────────────
# Report 7 — Expense Trend by Category
# ─────────────────────────────────────────────


def build_expense_trend(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return a category x month expense matrix."""
    from collections import defaultdict

    months = set()
    cat_month: dict = defaultdict(lambda: defaultdict(Decimal))
    income_month: dict = defaultdict(Decimal)

    for tx in transactions:
        tx_type = tx.get("type", "")
        amount = _d(tx.get("amount", 0))
        mk = str(tx.get("date", ""))[:7]
        cat = tx.get("category_name") or i18n.t("common.uncategorized")

        if not mk:
            continue
        months.add(mk)

        if tx_type == "withdrawal":
            cat_month[cat][mk] += amount
        elif tx_type == "deposit":
            income_month[mk] += amount

    sorted_months = sorted(months)

    # rows: categories sorted by descending total
    cat_totals = {cat: sum(vals.values()) for cat, vals in cat_month.items()}
    sorted_cats = sorted(cat_totals, key=lambda c: cat_totals[c], reverse=True)

    rows = []
    for cat in sorted_cats:
        monthly_vals = [cat_month[cat].get(mk, Decimal("0")) for mk in sorted_months]
        total = sum(monthly_vals)
        rows.append(
            {
                "category": cat,
                "monthly": monthly_vals,
                "total": total,
            }
        )

    totals_by_month = [
        sum(cat_month[cat].get(mk, Decimal("0")) for cat in sorted_cats) for mk in sorted_months
    ]
    income_row = [income_month.get(mk, Decimal("0")) for mk in sorted_months]

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "months": sorted_months,
        "rows": rows,
        "totals_by_month": totals_by_month,
        "income_by_month": income_row,
        "grand_total": sum(totals_by_month),
    }


# ─────────────────────────────────────────────
# Report 8 — Tagged Transactions Report
# ─────────────────────────────────────────────


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


# ─────────────────────────────────────────────
# Report 9 — Budget vs. Actual
# ─────────────────────────────────────────────


def build_budget_vs_actual(
    budgets: list[dict[str, Any]],
    budget_limits: dict[str, list[dict[str, Any]]],
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return budget planned vs actual spend per budget line."""
    from datetime import datetime

    actual_by_budget: dict = defaultdict(Decimal)
    unbudgeted = Decimal("0")

    # Calculate % of month elapsed
    now = datetime.now().date()
    if now < start:
        elapsed_pct = Decimal("0")
    elif now > end:
        elapsed_pct = Decimal("100")
    else:
        total_days = (end - start).days + 1
        elapsed_days = (now - start).days + 1
        elapsed_pct = (Decimal(elapsed_days) / Decimal(total_days) * 100).quantize(Decimal("0.1"))

    for tx in transactions:
        if tx.get("type") != "withdrawal":
            continue
        amount = _d(tx.get("amount", 0))
        budget = tx.get("budget_name") or tx.get("budget_id") or None
        if budget:
            actual_by_budget[str(budget)] += amount
        else:
            unbudgeted += amount

    rows = []
    total_limit = Decimal("0")
    total_actual = Decimal("0")

    for b in budgets:
        attrs = b.get("attributes", b)
        bid = str(b.get("id", ""))
        bname = attrs.get("name", "")
        auto_budget = attrs.get("auto_budget_amount")

        # prefer the period budget_limit if present, fall back to auto_budget_amount
        limits_list = budget_limits.get(bid, [])
        if limits_list:
            # sum all limits for the period (may be split monthly)
            limit_amount = sum(
                _d(lim.get("attributes", lim).get("amount", 0)) for lim in limits_list
            )
        elif auto_budget:
            limit_amount = _d(auto_budget)
        else:
            limit_amount = Decimal("0")

        # transactions carry budget_name, not budget_id
        actual = actual_by_budget.get(bname, Decimal("0"))

        variance = limit_amount - actual
        variance_pct = (
            (variance / limit_amount * 100).quantize(Decimal("0.1"))
            if limit_amount
            else Decimal("0")
        )
        spent_pct = (
            (actual / limit_amount * 100).quantize(Decimal("0.1")) if limit_amount else Decimal("0")
        )

        if limit_amount == 0:
            status = "no_limit"
            pace_status = "N/A"
        else:
            if actual > limit_amount:
                status = "over"
            elif actual >= limit_amount * Decimal("0.9"):
                status = "warning"
            else:
                status = "under"

            if spent_pct > elapsed_pct + 10:
                pace_status = "AHEAD"
            elif spent_pct < elapsed_pct - 10:
                pace_status = "UNDER"
            else:
                pace_status = "ON TRACK"

        rows.append(
            {
                "budget_name": bname,
                "limit": limit_amount,
                "actual": actual,
                "variance": variance,
                "variance_pct": variance_pct,
                "spent_pct": spent_pct,
                "status": status,
                "pace_status": pace_status,
            }
        )
        total_limit += limit_amount
        total_actual += actual

    rows.sort(key=lambda r: r["actual"], reverse=True)

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "total_limit": total_limit,
        "total_actual": total_actual,
        "total_variance": total_limit - total_actual,
        "unbudgeted_spending": unbudgeted,
        "elapsed_pct": elapsed_pct,
    }


# ─────────────────────────────────────────────
# Report 10 — Bills & Subscriptions
# ─────────────────────────────────────────────

_FREQ_KEYS = ("weekly", "monthly", "quarterly", "half-year", "yearly")


def _frequency_label(freq: str) -> str:
    """Translate a bill repeat frequency; unknown values pass through unchanged."""
    if freq in _FREQ_KEYS:
        return str(i18n.t(f"frequencies.{freq}"))
    return freq or "—"


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
        freq = _frequency_label(freq_raw)

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


# ─────────────────────────────────────────────
# Report 11 — Savings Goals (Piggy Banks)
# ─────────────────────────────────────────────


def build_savings_goals(
    piggy_banks: list[dict[str, Any]],
    as_of: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return savings goal progress for each piggy bank."""
    as_of_date = as_of
    from datetime import datetime

    goals = []
    total_saved = Decimal("0")
    total_target = Decimal("0")

    for pb in piggy_banks:
        attrs = pb.get("attributes", pb)

        target = _d(attrs.get("target_amount", 0))
        current = _d(attrs.get("current_amount", 0))
        pct = (current / target * 100).quantize(Decimal("0.1")) if target else Decimal("0")
        remaining = max(target - current, Decimal("0"))

        # monthly amount needed to reach the goal by the target date
        target_date_str = attrs.get("target_date") or ""
        monthly_needed = Decimal("0")
        months_left = None
        if target_date_str and remaining > 0:
            try:
                td = datetime.strptime(target_date_str[:10], "%Y-%m-%d").date()
                delta_months = max(
                    (td.year - as_of_date.year) * 12 + (td.month - as_of_date.month), 1
                )
                months_left = delta_months
                monthly_needed = (remaining / delta_months).quantize(Decimal("0.01"))
            except Exception:  # nosec B110
                pass

        # Linked account name: current API exposes `accounts[]` (v6.2+);
        # fall back to the legacy `account_name` / `account.name` fields.
        pb_accounts = attrs.get("accounts") or []
        account_name = (
            (pb_accounts[0].get("name", "") if pb_accounts else "")
            or attrs.get("account_name")
            or attrs.get("account", {}).get("name", "")
        )

        goals.append(
            {
                "name": attrs.get("name", ""),
                "target": target,
                "current": current,
                "remaining": remaining,
                "pct": pct,
                "start_date": (attrs.get("start_date") or "")[:10],
                "target_date": target_date_str[:10],
                "months_left": months_left,
                "monthly_needed": monthly_needed,
                "account_name": account_name,
                "notes": (attrs.get("notes") or "").strip()[:60],
            }
        )
        total_saved += current
        total_target += target

    goals.sort(key=lambda g: g["pct"], reverse=True)

    overall_pct = (
        (total_saved / total_target * 100).quantize(Decimal("0.1"))
        if total_target
        else Decimal("0")
    )

    return {
        "owner": owner_name,
        "as_of_date": as_of_date,
        "currency": currency_symbol,
        "goals": goals,
        "total_saved": total_saved,
        "total_target": total_target,
        "overall_pct": overall_pct,
        "goal_count": len(goals),
    }


# ─────────────────────────────────────────────
# Report 12 — Liabilities & Debt
# ─────────────────────────────────────────────

_LIAB_TYPES = ("loan", "debt", "mortgage")


def _liab_type_label(liab_type: str) -> str:
    """Translate a liability type; unknown types are capitalized, empty becomes 'other'."""
    if liab_type in _LIAB_TYPES:
        return str(i18n.t(f"liability_types.{liab_type}"))
    return liab_type.capitalize() if liab_type else i18n.t("liability_types.other")


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
        type_label = _liab_type_label(liab_type)
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


# ─────────────────────────────────────────────
# Report 13 — Financial KPI Scorecard
# ─────────────────────────────────────────────


def build_kpi_scorecard(
    transactions: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    liability_accounts: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return financial KPIs: burn rate, cash runway, savings rate, HHI."""

    total_in = Decimal("0")
    total_out = Decimal("0")
    income_by_client: dict = defaultdict(Decimal)
    by_month: dict = defaultdict(lambda: {"in": Decimal("0"), "out": Decimal("0")})

    for tx in transactions:
        t = tx.get("type", "")
        a = _d(tx.get("amount", 0))
        mk = str(tx.get("date", ""))[:7]
        if t == "deposit":
            total_in += a
            by_month[mk]["in"] += a
            client = tx.get("source_name") or "—"
            income_by_client[client] += a
        elif t == "withdrawal":
            total_out += a
            by_month[mk]["out"] += a

    n_months = max(len(by_month), 1)
    avg_monthly_in = (total_in / n_months).quantize(Decimal("0.01"))
    avg_monthly_out = (total_out / n_months).quantize(Decimal("0.01"))
    net_cash_flow = total_in - total_out

    savings_rate = (
        (net_cash_flow / total_in * 100).quantize(Decimal("0.1")) if total_in else Decimal("0")
    )
    burn_rate = avg_monthly_out

    liquid_assets = sum(
        _d(acc.get("attributes", acc).get("current_balance", 0))
        for acc in accounts
        if _d(acc.get("attributes", acc).get("current_balance", 0)) > 0
    )

    total_liab = sum(
        abs(_d(acc.get("attributes", acc).get("current_balance", 0))) for acc in liability_accounts
    )

    net_worth = liquid_assets - total_liab

    cash_runway = (
        (liquid_assets / burn_rate).quantize(Decimal("0.1")) if burn_rate else Decimal("0")
    )
    liquidity_ratio = (
        (liquid_assets / total_liab).quantize(Decimal("0.01"))
        if total_liab
        else None  # None = no liabilities
    )

    # Herfindahl-Hirschman Index for income concentration (0–10000)
    hhi = Decimal("0")
    if total_in > 0 and income_by_client:
        hhi = sum((amt / total_in * 100) ** 2 for amt in income_by_client.values()).quantize(
            Decimal("0.1")
        )

    top1_client = (
        max(income_by_client, key=lambda k: income_by_client[k]) if income_by_client else "—"
    )
    top1_pct = (
        (income_by_client[top1_client] / total_in * 100).quantize(Decimal("0.1"))
        if total_in and income_by_client
        else Decimal("0")
    )

    monthly_trend = []
    for mk in sorted(by_month):
        m_in = by_month[mk]["in"]
        m_out = by_month[mk]["out"]
        monthly_trend.append(
            {
                "month": mk,
                "income": m_in,
                "expense": m_out,
                "net": m_in - m_out,
            }
        )

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "total_in": total_in,
        "total_out": total_out,
        "net_cash_flow": net_cash_flow,
        "avg_monthly_in": avg_monthly_in,
        "avg_monthly_out": avg_monthly_out,
        "savings_rate": savings_rate,
        "burn_rate": burn_rate,
        "cash_runway": cash_runway,
        "liquid_assets": liquid_assets,
        "total_liab": total_liab,
        "net_worth": net_worth,
        "liquidity_ratio": liquidity_ratio,
        "hhi": hhi,
        "top1_client": top1_client,
        "top1_pct": top1_pct,
        "n_months": n_months,
        "monthly_trend": monthly_trend,
    }


# ─────────────────────────────────────────────
# Report 14 — Year-over-Year Comparison
# ─────────────────────────────────────────────


def _aggregate_period(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate income and expenses by category from a transaction list."""
    income: dict = defaultdict(Decimal)
    expense: dict = defaultdict(Decimal)
    for tx in transactions:
        t = tx.get("type", "")
        a = _d(tx.get("amount", 0))
        cat = tx.get("category_name") or i18n.t("common.uncategorized")
        if t == "deposit":
            income[cat] += a
        elif t == "withdrawal":
            expense[cat] += a
    return {"income": income, "expense": expense}


def build_yoy_comparison(
    transactions_cur: list[dict[str, Any]],
    transactions_prev: list[dict[str, Any]],
    start_cur: date,
    end_cur: date,
    start_prev: date,
    end_prev: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return year-over-year comparison of income and expenses by category."""
    transactions_a, transactions_b = transactions_cur, transactions_prev
    start_a, end_a = start_cur, end_cur
    start_b, end_b = start_prev, end_prev
    agg_a = _aggregate_period(transactions_a)
    agg_b = _aggregate_period(transactions_b)

    all_cats_income = set(agg_a["income"]) | set(agg_b["income"])
    all_cats_expense = set(agg_a["expense"]) | set(agg_b["expense"])

    def _rows(cats: set, d_a: dict, d_b: dict, tx_type: str) -> list:
        rows = []
        for cat in sorted(cats):
            va = d_a.get(cat, Decimal("0"))
            vb = d_b.get(cat, Decimal("0"))
            delta = va - vb
            delta_pct = (delta / vb * 100).quantize(Decimal("0.1")) if vb else Decimal("0")
            rows.append(
                {
                    "category": cat,
                    "type": tx_type,
                    "amount_a": va,
                    "amount_b": vb,
                    "delta": delta,
                    "delta_pct": delta_pct,
                }
            )
        return sorted(rows, key=lambda r: r["amount_a"], reverse=True)

    income_rows = _rows(all_cats_income, agg_a["income"], agg_b["income"], "income")
    expense_rows = _rows(all_cats_expense, agg_a["expense"], agg_b["expense"], "expense")

    total_in_a = sum(agg_a["income"].values()) or Decimal("0")
    total_in_b = sum(agg_b["income"].values()) or Decimal("0")
    total_out_a = sum(agg_a["expense"].values()) or Decimal("0")
    total_out_b = sum(agg_b["expense"].values()) or Decimal("0")

    def _delta_pct(a: Decimal, b: Decimal) -> Decimal:
        if b:
            return ((a - b) / b * 100).quantize(Decimal("0.1"))
        return Decimal("0")

    return {
        "owner": owner_name,
        "currency": currency_symbol,
        "period_a": {
            "start": start_a,
            "end": end_a,
            "label": f"{start_a.year}"
            if start_a.year == end_a.year
            else f"{start_a.strftime('%d/%m/%y')}–{end_a.strftime('%d/%m/%y')}",
        },
        "period_b": {
            "start": start_b,
            "end": end_b,
            "label": f"{start_b.year}"
            if start_b.year == end_b.year
            else f"{start_b.strftime('%d/%m/%y')}–{end_b.strftime('%d/%m/%y')}",
        },
        "income_rows": income_rows,
        "expense_rows": expense_rows,
        "total_in_a": total_in_a,
        "total_in_b": total_in_b,
        "total_out_a": total_out_a,
        "total_out_b": total_out_b,
        "net_a": total_in_a - total_out_a,
        "net_b": total_in_b - total_out_b,
        "delta_in_pct": _delta_pct(total_in_a, total_in_b),
        "delta_out_pct": _delta_pct(total_out_a, total_out_b),
    }


# ─────────────────────────────────────────────
# Report 15 — Cumulative Cash Flow
# ─────────────────────────────────────────────


def build_cumulative_cashflow(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return monthly cumulative cash flow series."""
    by_month: dict = defaultdict(lambda: {"in": Decimal("0"), "out": Decimal("0")})

    for tx in transactions:
        t = tx.get("type", "")
        a = _d(tx.get("amount", 0))
        mk = str(tx.get("date", ""))[:7]
        if not mk:
            continue
        if t == "deposit":
            by_month[mk]["in"] += a
        elif t == "withdrawal":
            by_month[mk]["out"] += a

    months_dict: dict = i18n.T.get("months", {})

    cumulative = Decimal("0")
    months = []
    for mk in sorted(by_month):
        y, m = mk.split("-")
        m_in = by_month[mk]["in"]
        m_out = by_month[mk]["out"]
        net = m_in - m_out
        cumulative += net
        months.append(
            {
                "month": mk,
                "month_label": f"{months_dict.get(m, m)} {y}",
                "income": m_in,
                "expense": m_out,
                "net": net,
                "cumulative": cumulative,
            }
        )

    peak_month = max(months, key=lambda m: m["cumulative"]) if months else None
    low_month = min(months, key=lambda m: m["cumulative"]) if months else None

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "months": months,
        "final_cumulative": cumulative,
        "peak_month": peak_month,
        "low_month": low_month,
    }


# ─────────────────────────────────────────────
# Report 16 — Income Concentration
# ─────────────────────────────────────────────


def build_income_concentration(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return income breakdown per client (revenue source account)."""
    client_data: dict = defaultdict(lambda: {"amount": Decimal("0"), "count": 0})
    monthly_by_client: dict = defaultdict(lambda: defaultdict(Decimal))

    for tx in transactions:
        if tx.get("type") != "deposit":
            continue
        a = _d(tx.get("amount", 0))
        client = tx.get("source_name") or i18n.t("common.unspecified")
        mk = str(tx.get("date", ""))[:7]
        client_data[client]["amount"] += a
        client_data[client]["count"] += 1
        monthly_by_client[client][mk] += a

    total_income = sum(d["amount"] for d in client_data.values()) or Decimal("0")

    rows = []
    for client, data in sorted(client_data.items(), key=lambda x: x[1]["amount"], reverse=True):
        pct = (
            (data["amount"] / total_income * 100).quantize(Decimal("0.1"))
            if total_income
            else Decimal("0")
        )
        rows.append(
            {
                "client": client,
                "amount": data["amount"],
                "pct": pct,
                "count": data["count"],
                "avg_per_tx": (data["amount"] / data["count"]).quantize(Decimal("0.01"))
                if data["count"]
                else Decimal("0"),
            }
        )

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "total_income": total_income,
        "client_count": len(rows),
    }


# ─────────────────────────────────────────────
# Report 17 — Transaction Audit Log
# ─────────────────────────────────────────────


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


# ─────────────────────────────────────────────
# Report 18 — Budget Performance Forecast
# ─────────────────────────────────────────────


def build_performance_forecast(
    budgets: list[dict[str, Any]],
    budget_limits: dict[str, list[dict[str, Any]]],
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Project month-end spending based on current velocity."""
    from datetime import datetime

    actual_by_budget: dict = defaultdict(Decimal)

    now = datetime.now().date()
    total_days = (end - start).days + 1
    if now < start:
        days_elapsed = 0
    elif now > end:
        days_elapsed = total_days
    else:
        days_elapsed = (now - start).days + 1

    for tx in transactions:
        if tx.get("type") != "withdrawal":
            continue
        amount = _d(tx.get("amount", 0))
        budget = tx.get("budget_name") or tx.get("budget_id") or None
        if budget:
            actual_by_budget[str(budget)] += amount

    rows = []
    for b in budgets:
        attrs = b.get("attributes", b)
        bid = str(b.get("id", ""))
        bname = attrs.get("name", "")

        limits_list = budget_limits.get(bid, [])
        if limits_list:
            limit_amount = sum(
                _d(lim.get("attributes", lim).get("amount", 0)) for lim in limits_list
            )
        else:
            limit_amount = _d(attrs.get("auto_budget_amount", 0))

        actual = actual_by_budget.get(bname, Decimal("0"))

        # Forecast: average daily spend * total days
        daily_avg = (actual / days_elapsed) if days_elapsed > 0 else Decimal("0")
        forecast = (daily_avg * total_days).quantize(Decimal("0.01"))
        variance = limit_amount - forecast

        status = "on_track"
        if limit_amount > 0:
            if forecast > limit_amount * Decimal("1.1"):
                status = "critical"
            elif forecast > limit_amount:
                status = "warning"
            elif forecast < limit_amount * Decimal("0.8"):
                status = "under"

        rows.append(
            {
                "budget_name": bname,
                "limit": limit_amount,
                "actual": actual,
                "daily_avg": daily_avg.quantize(Decimal("0.01")),
                "forecast": forecast,
                "variance": variance,
                "status": status,
            }
        )

    rows.sort(key=lambda r: r["forecast"], reverse=True)

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "rows": rows,
        "days_elapsed": days_elapsed,
        "total_days": total_days,
        "total_limit": sum(r["limit"] for r in rows),
        "total_actual": sum(r["actual"] for r in rows),
        "total_forecast": sum(r["forecast"] for r in rows),
    }


# ─────────────────────────────────────────────
# Report 19 — Category Ledger
# ─────────────────────────────────────────────


def build_category_ledger(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return transactions grouped and totaled by category (alphabetical)."""
    by_category: dict = defaultdict(list)

    for tx in transactions:
        tx_type = tx.get("type", "")
        if tx_type not in ("withdrawal", "deposit"):
            continue

        cat = tx.get("category_name") or i18n.t("common.uncategorized")
        amount = _d(tx.get("amount", 0))
        sign = -amount if tx_type == "withdrawal" else +amount

        by_category[cat].append(
            {
                "date": str(tx.get("date", ""))[:10],
                "description": tx.get("description", ""),
                "type": tx_type.capitalize(),
                "counterpart": (
                    tx.get("destination_name")
                    if tx_type == "withdrawal"
                    else tx.get("source_name", "")
                ),
                "amount": sign,
                "reconciled": tx.get("reconciled", False),
            }
        )

    sections = []
    for cat in sorted(by_category.keys()):
        rows = sorted(by_category[cat], key=lambda r: r["date"])
        sections.append(
            {
                "category_name": cat,
                "rows": rows,
                "total": sum(r["amount"] for r in rows),
                "count": len(rows),
            }
        )

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "sections": sections,
        "grand_total": sum(s["total"] for s in sections),
    }


# ─────────────────────────────────────────────
# Report 20 — Payee Ledger
# ─────────────────────────────────────────────


def build_payee_ledger(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return transactions grouped and totaled by payee (alphabetical)."""
    by_payee: dict = defaultdict(list)

    for tx in transactions:
        tx_type = tx.get("type", "")
        if tx_type not in ("withdrawal", "deposit"):
            continue

        payee = (
            tx.get("destination_name") if tx_type == "withdrawal" else tx.get("source_name", "")
        ) or i18n.t("common.unknown")

        amount = _d(tx.get("amount", 0))
        sign = -amount if tx_type == "withdrawal" else +amount

        by_payee[payee].append(
            {
                "date": str(tx.get("date", ""))[:10],
                "description": tx.get("description", ""),
                "type": tx_type.capitalize(),
                "category": tx.get("category_name") or "",
                "amount": sign,
                "reconciled": tx.get("reconciled", False),
            }
        )

    sections = []
    for payee in sorted(by_payee.keys()):
        rows = sorted(by_payee[payee], key=lambda r: r["date"])
        sections.append(
            {
                "payee_name": payee,
                "rows": rows,
                "total": sum(r["amount"] for r in rows),
                "count": len(rows),
            }
        )

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "sections": sections,
        "grand_total": sum(s["total"] for s in sections),
    }


# ─────────────────────────────────────────────
# Report 21 — Linkage & Reimbursement Report
# ─────────────────────────────────────────────


def build_linkage_report(
    transactions: list[dict[str, Any]],
    links: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Group linked transactions and calculate the linked amount % per group.

    ``links`` comes from GET /api/v1/transaction-links (via
    FireflyClient.get_transaction_links()): each link connects two transaction
    journal IDs. We group by outward_id (the original transaction, the parent);
    the inward side is the linked counterpart. All link types are included
    (Reimbursement, Refund, Paid, Related, custom); each group reports the
    link type name(s) and the linked amount as a percentage of the parent —
    meaningful as "recovery" for reimbursement-type links, a plain ratio
    otherwise.
    """
    tx_map = {str(tx.get("id") or tx.get("transaction_journal_id", "")): tx for tx in transactions}

    groups: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"parent": None, "children": [], "types": set()}
    )

    processed_links = set()

    for lnk in links:
        l_id = lnk.get("id")
        if l_id in processed_links:
            continue
        processed_links.add(l_id)

        in_id = str(lnk.get("inward_id", ""))
        out_id = str(lnk.get("outward_id", ""))

        # Parent is outward (the expense being reimbursed)
        # Child is inward (the incoming deposit)
        parent = tx_map.get(out_id)
        child = tx_map.get(in_id)

        lt_name = str(lnk.get("link_type_name") or "")
        if lt_name:
            groups[out_id]["types"].add(lt_name)
        if parent:
            groups[out_id]["parent"] = parent
        if child:
            groups[out_id]["children"].append(child)

    groups_list: list[dict[str, Any]] = []
    for out_id, data in groups.items():
        parent = data["parent"]
        if not parent:
            parent = tx_map.get(out_id)
            if not parent:
                continue

        p_amt = abs(_d(parent.get("amount", 0)))
        links_data = []
        total_reimbursed = Decimal("0")

        for c in data["children"]:
            c_amt = abs(_d(c.get("amount", 0)))
            total_reimbursed += c_amt
            links_data.append(
                {
                    "id": str(c.get("id") or c.get("transaction_journal_id", "")),
                    "date": str(c.get("date", ""))[:10],
                    "description": c.get("description", ""),
                    "category": c.get("category_name") or "",
                    "amount": c_amt,
                }
            )

        recovery_pct = (
            (total_reimbursed / p_amt * 100).quantize(Decimal("0.1")) if p_amt else Decimal("0")
        )

        groups_list.append(
            {
                "source": {
                    "id": str(parent.get("id") or parent.get("transaction_journal_id", "")),
                    "date": str(parent.get("date", ""))[:10],
                    "description": parent.get("description", ""),
                    "category": parent.get("category_name") or "",
                    "amount": -p_amt if parent.get("type") == "withdrawal" else p_amt,
                },
                "links": links_data,
                "link_types": ", ".join(sorted(data["types"])),
                "total_reimbursed": total_reimbursed,
                "recovery_pct": recovery_pct,
                "status": "Complete" if recovery_pct >= 99 else "Partial",
            }
        )

    groups_list.sort(key=lambda g: g["source"]["date"], reverse=True)

    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "groups": groups_list,
        "total_recovered": sum(g["total_reimbursed"] for g in groups_list),
    }


# ─────────────────────────────────────────────
# Report 22 — All Tags Ledger
# ─────────────────────────────────────────────


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


# ─────────────────────────────────────────────
# Report 23 — Multi-Year Historical Growth
# ─────────────────────────────────────────────


def build_historical_report(
    year_data: dict[int, dict[str, Any]],
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return year-over-year growth comparison across multiple years."""
    sorted_years = sorted(year_data.keys())

    rows = []
    for i, year in enumerate(sorted_years):
        data = year_data[year]
        income = _d(data.get("total_income", 0))
        expense = _d(data.get("total_expense", 0))
        net = _d(data.get("net_savings", 0))

        row = {
            "year": year,
            "income": income,
            "expense": expense,
            "net": net,
            "income_growth": Decimal("0"),
            "expense_growth": Decimal("0"),
            "net_growth": Decimal("0"),
        }

        if i > 0:
            prev_year = sorted_years[i - 1]
            prev_data = year_data[prev_year]

            prev_income = _d(prev_data.get("total_income", 0))
            prev_expense = _d(prev_data.get("total_expense", 0))
            prev_net = _d(prev_data.get("net_savings", 0))

            def calc_growth(current: Decimal, previous: Decimal) -> Decimal | None:
                if previous == 0:
                    return Decimal("0")
                return ((current - previous) / abs(previous) * 100).quantize(Decimal("0.1"))

            row["income_growth"] = calc_growth(income, prev_income)
            row["expense_growth"] = calc_growth(expense, prev_expense)
            row["net_growth"] = calc_growth(net, prev_net)

        rows.append(row)

    return {
        "owner": owner_name,
        "currency": currency_symbol,
        "rows": rows,
        "year_count": len(rows),
    }


# ─────────────────────────────────────────────
# Report 24 — Liquidity Forecast (6 Months)
# ─────────────────────────────────────────────


def build_liquidity_forecast(
    current_balance: Decimal,
    avg_income: Decimal,
    avg_variable_expense: Decimal,
    bills: list[dict[str, Any]],
    end_date: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Project 6-month liquidity forecast starting from the month after end_date."""
    from dateutil.relativedelta import relativedelta

    months = []
    running_balance = _d(current_balance)
    inc = _d(avg_income)
    var = _d(avg_variable_expense)

    # Forecast starts from the month after end_date
    start_forecast = end_date.replace(day=1) + relativedelta(months=1)

    for i in range(6):
        target_date = start_forecast + relativedelta(months=i)

        # Calculate Monthly Fixed Expense (Bills)
        monthly_fixed = Decimal("0")
        for b in bills:
            attrs = b.get("attributes", b)
            if not attrs.get("active", True):
                continue

            # expected amount
            amount_min = _d(attrs.get("amount_min", 0))
            amount_max = _d(attrs.get("amount_max", 0))
            expected = ((amount_min + amount_max) / 2).quantize(Decimal("0.01"))

            # check if bill hits this month
            freq = attrs.get("repeat_freq")
            next_date_str = attrs.get("next_expected_match")

            hits = False
            if not next_date_str:
                if freq == "monthly":
                    hits = True
            else:
                try:
                    next_date = date.fromisoformat(next_date_str[:10])
                    next_m = next_date.replace(day=1)
                    target_m = target_date.replace(day=1)

                    if freq == "monthly" or freq == "weekly" or next_m == target_m:
                        hits = True
                    elif next_m < target_m:
                        # project forward
                        curr = next_m
                        while curr <= target_m:
                            if curr == target_m:
                                hits = True
                                break
                            if freq == "quarterly":
                                curr += relativedelta(months=3)
                            elif freq == "half-year":
                                curr += relativedelta(months=6)
                            elif freq == "yearly":
                                curr += relativedelta(years=1)
                            else:
                                break
                except Exception:
                    if freq == "monthly":
                        hits = True

            if hits:
                monthly_fixed += expected

        # Accumulate: New Balance = Previous Balance + Income - Fixed - Variable
        outflow = monthly_fixed + var
        running_balance = running_balance + inc - outflow

        month_name = i18n.T.get("months", {}).get(
            f"{target_date.month:02d}", target_date.strftime("%m")
        )
        months.append(
            {
                "month": target_date.strftime("%Y-%m"),
                "month_label": f"{month_name} {target_date.year}",
                "inflow": inc,
                "outflow": outflow,
                "fixed_outflow": monthly_fixed,
                "variable_outflow": var,
                "balance": running_balance,
            }
        )

    return {
        "owner": owner_name,
        "currency": currency_symbol,
        "start_date": end_date,
        "forecast_months": months,
        "final_balance": running_balance,
        "avg_income": inc,
        "avg_variable": var,
    }


# ─────────────────────────────────────────────
# Report 25 — General Journal (Libro Giornale, R-ITA-06)
# ─────────────────────────────────────────────


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


# ─────────────────────────────────────────────
# Report 26 — Instance & Period Summary
# ─────────────────────────────────────────────


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
