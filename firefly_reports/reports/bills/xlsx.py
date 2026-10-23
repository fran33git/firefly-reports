"""Excel sheet of the bills report."""

from typing import Any

from openpyxl import Workbook

from firefly_reports.i18n import t
from firefly_reports.render.fmt import period_str
from firefly_reports.render.xlsx.layout import (
    data_row,
    header_row,
    title_block,
    to_number,
)

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────


def write_sheet(wb: Workbook, data: dict[str, Any]) -> None:
    ws = wb.create_sheet(t("excel.sheet_bills"))
    period = period_str(data["period_start"], data["period_end"])
    row = title_block(ws, t("titles.bills"), data["owner"], period)
    sym = data["currency"]

    row = header_row(
        ws,
        row,
        [
            t("common.name"),
            t("common.frequency"),
            t("excel.col_bills_expected").format(sym=sym),
            f"{t('common.paid')} ({sym})",
            t("excel.col_bills_count"),
            t("excel.col_bills_last"),
        ],
        col_widths=[28, 14, 16, 16, 14, 16],
    )

    for r in data["rows"]:
        row = data_row(
            ws,
            row,
            [
                r["name"],
                r["frequency"],
                to_number(r["expected"]),
                to_number(r["paid_amount"]),
                r["times_paid"],
                r["last_paid"] or "—",
            ],
        )

    row = data_row(
        ws,
        row,
        [
            t("common.total"),
            "",
            to_number(data["total_expected"]),
            to_number(data["total_paid"]),
            "",
            "",
        ],
        is_total=True,
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
