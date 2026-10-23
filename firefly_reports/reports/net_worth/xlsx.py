"""Excel sheet of the net_worth report."""

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_date
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
    ws = wb.create_sheet(t("excel.sheet_net_worth"))
    as_of = fmt_date(data["as_of_date"])
    row = title_block(
        ws, t("excel.sheet_net_worth"), data["owner"], t("pdf.as_of").format(date=as_of)
    )

    sym = data["currency"]

    for group in data["groups"]:
        if not group["accounts"]:
            continue
        ws.merge_cells(f"A{row}:H{row}")
        ws.cell(row=row, column=1, value=group["role_label"].upper()).font = Font(
            name="Calibri", bold=True, size=9, color=LIGHT_HEX
        )
        ws.row_dimensions[row].height = 20
        row += 1

        row = header_row(
            ws,
            row,
            [
                t("common.account"),
                t("common.iban_masked"),
                t("common.currency_col"),
                f"{t('common.balance')} ({sym})",
            ],
            col_widths=[32, 22, 10, 18],
        )
        for acc in group["accounts"]:
            row = data_row(
                ws,
                row,
                [acc["name"], acc["iban_masked"], acc["currency_code"], to_number(acc["balance"])],
                indent_col=1,
            )

        row = data_row(
            ws,
            row,
            [
                t("pdf.subtotal").format(role=group["role_label"]),
                "",
                "",
                to_number(group["subtotal"]),
            ],
            is_total=True,
        )
        row += 1

    row = data_row(
        ws,
        row,
        [t("excel.total_assets_short"), "", "", to_number(data["total_assets"])],
        is_total=True,
    )
    row = data_row(
        ws,
        row,
        [t("excel.total_liabilities_short"), "", "", to_number(data["total_liabilities"])],
        is_total=True,
    )
    row = data_row(
        ws, row, [t("common.net_worth"), "", "", to_number(data["net_worth"])], is_grand=True
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
