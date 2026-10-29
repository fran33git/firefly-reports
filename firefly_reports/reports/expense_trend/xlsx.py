"""Excel sheet of the expense_trend report."""

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import period_str
from firefly_reports.render.xlsx.layout import (
    data_row,
    header_row,
    title_block,
    to_number,
)
from firefly_reports.render.xlsx.styles import (
    MID_HEX,
    thin,
)

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────


def write_sheet(wb: Workbook, data: dict[str, Any]) -> None:
    ws = wb.create_sheet(t("excel.sheet_expense_trend"))
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    months = data["months"]

    row = title_block(ws, t("titles.expense_trend"), data["owner"], period)

    months_abbr = i18n.current().section("months_abbr")

    def _mk(mk: str) -> str:
        y, m = mk.split("-")
        return f"{months_abbr.get(m, m)} {y[-2:]}"

    headers = [t("common.category")] + [_mk(m) for m in months] + [f"{t('common.total')} ({sym})"]
    col_widths = [32] + [11] * len(months) + [16]
    row = header_row(ws, row, headers, col_widths=col_widths)

    for r in data["rows"]:
        vals = (
            [r["category"]]
            + [to_number(v) if v > 0 else None for v in r["monthly"]]
            + [to_number(r["total"])]
        )
        for col_idx, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col_idx, value=val)
            c.font = Font(name="Calibri", size=9.5)
            c.alignment = Alignment(
                horizontal="right" if col_idx > 1 else "left", vertical="center"
            )
            if val is not None and col_idx > 1:
                c.number_format = "#,##0.00"
            c.border = Border(bottom=thin("EEEEEE"))
        ws.row_dimensions[row].height = 16
        row += 1

    # Expense total row
    tot_vals = (
        [t("excel.total_expense_matrix")]
        + [to_number(v) for v in data["totals_by_month"]]
        + [to_number(data["grand_total"])]
    )
    row = data_row(ws, row, tot_vals, is_total=True)

    # Income comparison row
    inc_vals = (
        [t("excel.income_for_comparison")]
        + [to_number(v) for v in data["income_by_month"]]
        + [to_number(sum(data["income_by_month"]))]
    )
    for col_idx, val in enumerate(inc_vals, start=1):
        c = ws.cell(row=row, column=col_idx, value=val)
        c.font = Font(name="Calibri", size=9.5, italic=True, color=MID_HEX)
        c.alignment = Alignment(horizontal="right" if col_idx > 1 else "left", vertical="center")
        if col_idx > 1 and isinstance(val, float):
            c.number_format = "#,##0.00"
        c.border = Border(top=thin())
    ws.row_dimensions[row].height = 18

    ws.freeze_panes = f"B{row - len(data['rows']) - 3}"
    ws.sheet_view.showGridLines = False
