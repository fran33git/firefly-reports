"""Excel sheet of the income_concentration report."""

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
    ws = wb.create_sheet(t("excel.sheet_concentration"))
    period = period_str(data["period_start"], data["period_end"])
    row = title_block(ws, t("titles.income_concentration"), data["owner"], period)
    sym = data["currency"]

    row = header_row(
        ws,
        row,
        [
            t("common.income_client"),
            f"{t('common.amount')} ({sym})",
            t("excel.col_income_conc_share"),
            t("excel.col_income_conc_count"),
            t("excel.col_income_conc_avg").format(sym=sym),
        ],
        col_widths=[30, 16, 14, 14, 18],
    )

    for r in data["rows"]:
        row = data_row(
            ws,
            row,
            [
                r["client"],
                to_number(r["amount"]),
                float(r["pct"]) / 100,
                r["count"],
                to_number(r["avg_per_tx"]),
            ],
            indent_col=1,
        )
        ws.cell(row=row - 1, column=3).number_format = "0.0%"

    row = data_row(
        ws, row, [t("common.total"), to_number(data["total_income"]), 1.0, "", ""], is_total=True
    )
    ws.cell(row=row - 1, column=3).number_format = "0.0%"
