"""Excel sheet of the savings_goals report."""

from typing import Any

from openpyxl import Workbook

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_date
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
    ws = wb.create_sheet(t("excel.sheet_savings"))
    as_of = fmt_date(data["as_of_date"])
    row = title_block(
        ws, t("titles.savings_goals"), data["owner"], t("pdf.as_of").format(date=as_of)
    )
    sym = data["currency"]

    row = header_row(
        ws,
        row,
        [
            t("common.objective"),
            t("common.target") + f" ({sym})",
            t("excel.col_savings_reached").format(sym=sym),
            t("excel.col_savings_remaining").format(sym=sym),
            t("excel.col_savings_progress"),
            t("excel.col_savings_deadline"),
            t("excel.col_savings_monthly").format(sym=sym),
        ],
        col_widths=[28, 16, 16, 16, 14, 14, 16],
    )

    for g in data["goals"]:
        row = data_row(
            ws,
            row,
            [
                g["name"],
                to_number(g["target"]),
                to_number(g["current"]),
                to_number(g["remaining"]),
                float(g["pct"]) / 100,
                g["target_date"] or "—",
                to_number(g["monthly_needed"]) if g["monthly_needed"] > 0 else None,
            ],
        )
        ws.cell(row=row - 1, column=5).number_format = "0.0%"

    row = data_row(
        ws,
        row,
        [
            t("common.total"),
            to_number(data["total_target"]),
            to_number(data["total_saved"]),
            to_number(data["total_target"] - data["total_saved"]),
            float(data["overall_pct"]) / 100,
            "",
            "",
        ],
        is_total=True,
    )
    ws.cell(row=row - 1, column=5).number_format = "0.0%"

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
