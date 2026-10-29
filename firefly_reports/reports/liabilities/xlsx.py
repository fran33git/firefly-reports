"""Excel sheet of the liabilities report."""

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
    ws = wb.create_sheet(t("excel.sheet_liabilities"))
    as_of = fmt_date(data["as_of_date"])
    row = title_block(ws, t("titles.liabilities"), data["owner"], t("pdf.as_of").format(date=as_of))
    sym = data["currency"]

    row = header_row(
        ws,
        row,
        [
            t("excel.col_liab_name"),
            t("excel.col_liab_type"),
            t("excel.col_liab_balance").format(sym=sym),
            t("excel.col_liab_rate"),
            t("common.currency_col"),
            t("excel.col_liab_payments").format(sym=sym),
        ],
        col_widths=[28, 16, 20, 10, 10, 20],
    )

    for r in data["rows"]:
        row = data_row(
            ws,
            row,
            [
                r["name"],
                r["type"],
                to_number(r["debt_amount"]),
                float(r["interest_rate"]) if r["interest_rate"] else None,
                r["currency_code"],
                to_number(r["period_payments"]) if r["period_payments"] else None,
            ],
        )

    row = data_row(
        ws,
        row,
        [
            t("common.total_liabilities"),
            "",
            to_number(data["total_debt"]),
            "",
            "",
            to_number(data["total_payments"]),
        ],
        is_grand=True,
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
