"""Excel sheet of the income_expense report."""

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from firefly_reports.i18n import t
from firefly_reports.render.fmt import period_str
from firefly_reports.render.xlsx.layout import (
    data_row,
    header_row,
    title_block,
    to_number,
)
from firefly_reports.render.xlsx.styles import (
    LIGHT_HEX,
)

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────


def write_sheet(wb: Workbook, data: dict[str, Any]) -> None:
    ws = wb.create_sheet(t("excel.sheet_income"))
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]

    row = title_block(ws, t("excel.sheet_income"), data["owner"], period)

    # Income
    ws.merge_cells(f"A{row}:H{row}")
    ws.cell(row=row, column=1, value=t("pdf.section_income_cat")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 22
    row += 1

    row = header_row(
        ws,
        row,
        [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")],
        col_widths=[40, 18, 16],
    )
    for r in data["income_rows"]:
        row = data_row(
            ws, row, [r["category"], to_number(r["amount"]), float(r["pct"])], indent_col=1
        )
    row = data_row(
        ws, row, [t("common.total_income"), to_number(data["total_income"]), 100.0], is_total=True
    )
    ws.cell(row=row - 1, column=3).number_format = '0.0"%"'

    row += 1

    # Expenses
    ws.merge_cells(f"A{row}:H{row}")
    ws.cell(row=row, column=1, value=t("pdf.section_expense_cat")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 22
    row += 1

    row = header_row(
        ws, row, [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")]
    )
    for r in data["expense_rows"]:
        row = data_row(
            ws, row, [r["category"], to_number(r["amount"]), float(r["pct"])], indent_col=1
        )
    row = data_row(
        ws, row, [t("common.total_expense"), to_number(data["total_expense"]), 100.0], is_total=True
    )

    row += 1

    # Budget
    if data["budget_breakdown"]:
        ws.merge_cells(f"A{row}:H{row}")
        ws.cell(row=row, column=1, value=t("pdf.section_summary_analysis")).font = Font(
            name="Calibri", bold=True, size=9, color=LIGHT_HEX
        )
        ws.row_dimensions[row].height = 22
        row += 1
        row = header_row(ws, row, [t("common.budget"), f"{t('common.amount')} ({sym})"])
        for b in data["budget_breakdown"]:
            row = data_row(ws, row, [b["budget"], to_number(b["spent"])], indent_col=1)
        row += 1

    # Grand total
    row = data_row(
        ws,
        row,
        [t("common.net_savings"), to_number(data["net_savings"]), float(data["savings_rate"])],
        is_grand=True,
    )
    ws.cell(row=row - 1, column=3).number_format = '0.0"%"'

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
