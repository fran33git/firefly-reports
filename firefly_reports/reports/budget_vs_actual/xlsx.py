"""Excel sheet of the budget_vs_actual report."""

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
    ws = wb.create_sheet(t("excel.sheet_budget"))
    period = period_str(data["period_start"], data["period_end"])
    row = title_block(ws, t("titles.budget_vs_actual_report"), data["owner"], period)
    sym = data["currency"]

    row = header_row(
        ws,
        row,
        [
            t("common.budget"),
            t("excel.col_budget_limit").format(sym=sym),
            t("excel.col_budget_actual").format(sym=sym),
            t("excel.col_budget_variance").format(sym=sym),
            t("excel.col_budget_variance_pct"),
        ],
        col_widths=[30, 16, 16, 18, 14],
    )

    for r in data["rows"]:
        var = float(r["variance"])
        row = data_row(
            ws,
            row,
            [
                r["budget_name"],
                to_number(r["limit"]),
                to_number(r["actual"]),
                var,
                float(r["variance_pct"]) / 100,
            ],
        )
        ws.cell(row=row - 1, column=5).number_format = "0.0%"

    row = data_row(
        ws,
        row,
        [
            t("pdf.budgeted_total"),
            to_number(data["total_limit"]),
            to_number(data["total_actual"]),
            to_number(data["total_variance"]),
            "",
        ],
        is_total=True,
    )

    if data["unbudgeted_spending"] > 0:
        row += 1
        row = data_row(
            ws, row, [t("excel.unbudgeted"), to_number(data["unbudgeted_spending"])], is_total=True
        )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
