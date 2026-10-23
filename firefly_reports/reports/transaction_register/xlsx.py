"""Excel sheet of the transaction_register report."""

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import flatten_rows, period_str
from firefly_reports.render.xlsx.layout import (
    data_row,
    header_row,
    title_block,
    to_number,
)
from firefly_reports.render.xlsx.styles import (
    LIGHT_HEX,
    thin,
)

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────


def write_sheet(wb: Workbook, data: dict[str, Any]) -> None:
    ws = wb.create_sheet(t("excel.sheet_register"))
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]

    row = title_block(ws, t("excel.sheet_register"), data["owner"], period)

    headers = [
        t("common.date"),
        t("common.description"),
        t("common.type"),
        t("common.category"),
        t("common.budget"),
        f"{t('common.amount')} ({sym})",
        f"{t('common.running_balance')} ({sym})",
    ]
    col_widths = [12, 38, 12, 22, 18, 16, 18]
    row = header_row(ws, row, headers, col_widths=col_widths)

    current_month = None
    months_it = i18n.current().section("months")

    flat_rows = flatten_rows(data["rows"])
    for r in flat_rows:
        mk = r["date"][:7]
        if mk != current_month:
            current_month = mk
            y, m = mk.split("-")
            # month separator row
            ws.merge_cells(f"A{row}:G{row}")
            c = ws.cell(row=row, column=1, value=f"{months_it.get(m, m)} {y}".upper())
            c.font = Font(name="Calibri", bold=True, size=8.5, color=LIGHT_HEX)
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.border = Border(bottom=thin())
            ws.row_dimensions[row].height = 16
            row += 1

        vals = [
            r["date"],
            r["description"],
            r["type"][:3].upper(),
            r["category"] or "—",
            r["budget"] or "—",
            to_number(r["amount"]),
            to_number(r["running_balance"]),
        ]
        for col_idx, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col_idx, value=val)
            c.font = Font(name="Calibri", size=9.5)
            is_num = col_idx in [6, 7]
            c.alignment = Alignment(horizontal="right" if is_num else "left", vertical="center")
            if is_num:
                c.number_format = "#,##0.00"
            c.border = Border(bottom=thin("EEEEEE"))
        ws.row_dimensions[row].height = 16
        row += 1

    # Final balance row
    if data["rows"]:
        final_bal = to_number(data["rows"][-1]["running_balance"])
        row = data_row(
            ws, row, ["", t("pdf.closing_balance_period"), "", "", "", "", final_bal], is_grand=True
        )

    ws.auto_filter.ref = f"A{row - len(data['rows']) - 2}:G{row - 1}"
    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
