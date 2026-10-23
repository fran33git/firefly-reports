"""Excel sheet of the account_statements report."""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font

from firefly_reports.i18n import t
from firefly_reports.render.fmt import flatten_rows, period_str
from firefly_reports.render.xlsx.layout import (
    data_row,
    header_row,
    safe_sheet_name,
    title_block,
    to_number,
)
from firefly_reports.render.xlsx.styles import (
    body_font,
    thin,
)

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────


def write_sheet(wb: Workbook, statements: list):
    for stmt in statements:
        sheet_name = safe_sheet_name(f"{t('common.account')} {stmt['account_name']}")
        ws = wb.create_sheet(sheet_name)
        period = period_str(stmt["period_start"], stmt["period_end"])
        sym = stmt["currency"]

        row = title_block(
            ws, f"{t('common.account')} {stmt['account_name']}", stmt["owner"], period
        )

        # Account metadata
        ws.cell(row=row, column=1, value="IBAN").font = body_font(bold=True, size=9)
        ws.cell(row=row, column=2, value=stmt["account_iban"]).font = body_font(size=9)
        ws.row_dimensions[row].height = 16
        row += 1
        ws.cell(row=row, column=1, value=t("common.opening_balance")).font = body_font(
            bold=True, size=9
        )
        ws.cell(
            row=row, column=2, value=to_number(stmt["opening_balance"])
        ).number_format = "#,##0.00"
        ws.cell(row=row, column=2).font = body_font(size=9)
        ws.row_dimensions[row].height = 16
        row += 2

        headers = [
            t("common.date"),
            t("common.description"),
            t("common.type"),
            t("common.counterpart"),
            t("common.category"),
            f"{t('common.amount')} ({sym})",
            f"{t('common.running_balance')} ({sym})",
        ]
        col_widths = [12, 38, 10, 24, 22, 16, 18]
        row = header_row(ws, row, headers, col_widths=col_widths)

        flat_stmt_rows = flatten_rows(stmt["rows"])
        for r in flat_stmt_rows:
            vals = [
                r["date"],
                r["description"],
                r["type"][:3].upper(),
                r["counterpart"] or "—",
                r["category"] or "—",
                to_number(r["amount"]),
                to_number(r["running_balance"]),
            ]
            for col_idx, val in enumerate(vals, start=1):
                c = ws.cell(row=row, column=col_idx, value=val)
                c.font = Font(name="Calibri", size=9.5)
                c.alignment = Alignment(
                    horizontal="right" if col_idx in [6, 7] else "left", vertical="center"
                )
                if col_idx in [6, 7]:
                    c.number_format = "#,##0.00"
                c.border = Border(bottom=thin("EEEEEE"))
            ws.row_dimensions[row].height = 16
            row += 1

        row = data_row(
            ws,
            row,
            [
                "",
                t("excel.closing_balance_short"),
                "",
                "",
                "",
                "",
                to_number(stmt["closing_balance"]),
            ],
            is_grand=True,
        )

        ws.freeze_panes = "A8"
        ws.sheet_view.showGridLines = False
