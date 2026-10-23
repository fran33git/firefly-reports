"""Excel sheet of the cumulative_cashflow report."""

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


def write_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_cumulative"))
    period = period_str(data["period_start"], data["period_end"])
    row = title_block(ws, t("titles.cumulative_cash_flow"), data["owner"], period)
    sym = data["currency"]

    row = header_row(
        ws,
        row,
        [
            t("common.month"),
            f"{t('common.income')} ({sym})",
            f"{t('common.expense')} ({sym})",
            f"{t('excel.col_cumulative_net_month')} ({sym})",
            f"{t('excel.col_cumulative_prog')} ({sym})",
        ],
        col_widths=[20, 16, 16, 16, 20],
    )

    for m in data["months"]:
        row = data_row(
            ws,
            row,
            [
                m["month_label"],
                to_number(m["income"]),
                to_number(m["expense"]),
                to_number(m["net"]),
                to_number(m["cumulative"]),
            ],
        )

    row = data_row(
        ws,
        row,
        [t("pdf.cumulative_final"), "", "", "", to_number(data["final_cumulative"])],
        is_grand=True,
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
