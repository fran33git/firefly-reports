"""Builder of the linkage_audit report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


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


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    p, o = ctx.period, ctx.options
    return build_linkage_report(
        src.transactions + src.linked_extra, src.links, p.start, p.end, o.owner, o.currency
    )
