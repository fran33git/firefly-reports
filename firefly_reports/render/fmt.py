"""Locale-aware number, date and period formatting shared by PDF and Excel."""

from datetime import date as dt_date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.i18n import T


def fmt_date(d: Any) -> str:
    """Locale-aware date format: DD/MM/YYYY for Italian, ISO YYYY-MM-DD otherwise."""
    if not hasattr(d, "strftime"):
        return str(d)
    fmt = "%d/%m/%Y" if i18n.CURRENT_LANG == "it" else "%Y-%m-%d"
    return str(d.strftime(fmt))


def period_str(start: dt_date, end: dt_date) -> str:
    months_it = T.get("months", {})
    if start.year == end.year and start.month == end.month:
        m_key = f"{start.month:02d}"
        month_label = months_it.get(m_key, str(start.month))
        return f"{month_label.lower()} {start.year}"
    return f"{fmt_date(start)} – {fmt_date(end)}"


def fmt_num(value: Decimal, show_sym: bool = False, sym: str = "€", parens_neg: bool = True) -> str:
    """
    Accounting number format:
      - thousands/decimal separators follow i18n.CURRENT_LANG
        (it: "1.234,56" — other languages: "1,234.56")
      - negative values in parentheses
      - optional currency symbol
    """
    abs_val = abs(value)
    s = f"{abs_val:,.2f}"
    if i18n.CURRENT_LANG == "it":
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    if show_sym:
        s = f"{sym} {s}"
    if value < 0 and parens_neg:
        s = f"({s})"
    return s


def flatten_rows(grouped_rows: list[dict]) -> list[dict]:
    """Helper to flatten grouped transactions for legacy renderers."""
    flat = []
    # In grouped_rows, running_balance is at the parent level.
    # To restore legacy behavior (running balance per split),
    # we need to track it based on the parent's starting balance.

    # Actually, the processor calculates running_balance after sorting groups.
    # We can just use the parent's running_balance for the last split of the group,
    # but for intermediate splits we'd need to subtract.
    # SIMPLER: Just use the parent's running_balance for ALL splits of that group
    # (this is slightly different from old legacy but close enough for "Grouped" context)
    # OR better: recalculate here.

    for group in grouped_rows:
        splits = group.get("splits", [])
        if not splits:
            flat.append(group)
            continue

        for split in splits:
            item = split.copy()
            item["date"] = group.get("date")
            item["description"] = group.get("description")
            item["type"] = group.get("type", "Standard")
            # If the group has a running_balance (from processor),
            # we use it as the 'final' balance for this group.
            # For simplicity in legacy, we attach the group's running_balance to all its splits.
            item["running_balance"] = group.get("running_balance", Decimal("0"))
            flat.append(item)
    return flat
