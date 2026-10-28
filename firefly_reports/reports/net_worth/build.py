"""Builder of the net_worth report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._labels import (
    ROLE_ORDER,
    account_role_label,
)
from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


def build_net_worth(
    accounts: list[dict[str, Any]],
    as_of: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return net worth grouped by account type."""
    as_of_date = as_of

    groups: dict = defaultdict(list)

    for acc in accounts:
        attrs = acc.get("attributes", acc)  # supports both raw API items and flat dicts
        role = attrs.get("account_role") or ""
        label = account_role_label(role)
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
    order = [account_role_label(r) for r in ROLE_ORDER]
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


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    p, o = ctx.period, ctx.options
    return build_net_worth(src.accounts, p.end, o.owner, o.currency)
