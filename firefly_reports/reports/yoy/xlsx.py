"""Excel sheet of the yoy report."""

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from firefly_reports.i18n import t
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
    ws = wb.create_sheet(t("excel.sheet_yoy"))
    la, lb = data["period_a"]["label"], data["period_b"]["label"]
    row = title_block(ws, t("titles.yoy_comparison"), data["owner"], f"{lb} vs {la}")
    sym = data["currency"]

    for section_title, rows_data, tot_a, tot_b in [
        (t("common.income").upper(), data["income_rows"], data["total_in_a"], data["total_in_b"]),
        (
            t("common.expense").upper(),
            data["expense_rows"],
            data["total_out_a"],
            data["total_out_b"],
        ),
    ]:
        ws.cell(row=row, column=1, value=section_title).font = Font(
            name="Calibri", bold=True, size=9, color=LIGHT_HEX
        )
        ws.row_dimensions[row].height = 20
        row += 1

        row = header_row(
            ws,
            row,
            [
                t("common.category"),
                f"{la} ({sym})",
                f"{lb} ({sym})",
                t("pdf.delta_absolute") + f" ({sym})",
                t("pdf.delta_pct"),
            ],
            col_widths=[30, 16, 16, 16, 12],
        )

        for r in rows_data:
            dpct = float(r["delta_pct"]) / 100 if r["amount_b"] else None
            row = data_row(
                ws,
                row,
                [
                    r["category"],
                    to_number(r["amount_a"]),
                    to_number(r["amount_b"]),
                    to_number(r["delta"]),
                    dpct,
                ],
                indent_col=1,
            )
            if dpct is not None:
                ws.cell(row=row - 1, column=5).number_format = "0.0%"

        dpct_tot = float((tot_a - tot_b) / tot_b * 100) / 100 if tot_b else None
        row = data_row(
            ws,
            row,
            [
                t("common.total"),
                to_number(tot_a),
                to_number(tot_b),
                to_number(tot_a - tot_b),
                dpct_tot,
            ],
            is_total=True,
        )
        if dpct_tot is not None:
            ws.cell(row=row - 1, column=5).number_format = "0.0%"
        row += 1

    row = data_row(
        ws,
        row,
        [
            t("common.net_flow"),
            to_number(data["net_a"]),
            to_number(data["net_b"]),
            to_number(data["net_a"] - data["net_b"]),
            "",
        ],
        is_grand=True,
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
