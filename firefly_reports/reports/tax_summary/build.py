"""Builder of the tax_summary report (pure: no I/O, Decimal money)."""

from collections import defaultdict
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d


def build_tax_summary(
    transactions: list[dict[str, Any]],
    year: int,
    owner_name: str = "",
    currency_symbol: str = "EUR",
    professional_income_categories: list | None = None,
    deductible_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Return cash-basis tax summary: deductible expenses and taxable income."""

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
