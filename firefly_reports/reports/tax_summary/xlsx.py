"""Excel sheet of the tax_summary report."""

from decimal import Decimal

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


def write_sheet(wb: Workbook, data: dict):
    ws = wb.create_sheet(t("excel.sheet_tax"))
    sym = data["currency"]
    row = title_block(
        ws, t("titles.tax_summary"), data["owner"], t("pdf.fiscal_year").format(year=data["year"])
    )

    # Income by category
    ws.cell(row=row, column=1, value=t("pdf.section_tax_income")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 20
    row += 1
    row = header_row(
        ws,
        row,
        [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")],
        col_widths=[38, 18, 14],
    )
    for r in data["income_by_cat"]:
        row = data_row(
            ws,
            row,
            [
                r["category"],
                to_number(r["amount"]),
                float((r["amount"] / data["total_income"] * 100).quantize(Decimal("0.1")))
                if data["total_income"]
                else 0.0,
            ],
            indent_col=1,
        )
    row = data_row(
        ws,
        row,
        [t("excel.total_income_section"), to_number(data["total_income"]), 100.0],
        is_total=True,
    )
    row += 1

    # Income by client
    ws.cell(
        row=row,
        column=1,
        value=f"{t('pdf.section_tax_income')} — {t('common.counterpart').upper()}",
    ).font = Font(name="Calibri", bold=True, size=9, color=LIGHT_HEX)
    ws.row_dimensions[row].height = 20
    row += 1
    row = header_row(ws, row, [t("common.income_client"), f"{t('common.amount')} ({sym})"])
    for r in data["income_by_client"]:
        row = data_row(ws, row, [r["client"], to_number(r["amount"])], indent_col=1)
    row += 1

    # Deductible expenses
    ws.cell(row=row, column=1, value=t("pdf.section_tax_deductible")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 20
    row += 1
    row = header_row(ws, row, [t("common.category"), f"{t('common.amount')} ({sym})"])
    for r in data["deductible_rows"]:
        row = data_row(ws, row, [r["category"], to_number(r["amount"])], indent_col=1)
    row = data_row(
        ws,
        row,
        [t("excel.total_deductible_short"), to_number(data["total_deductible"])],
        is_total=True,
    )
    row += 1

    # Tax summary
    row = data_row(
        ws, row, [t("excel.total_income_section"), to_number(data["total_income"])], is_total=True
    )
    row = data_row(
        ws,
        row,
        [f"- {t('excel.total_deductible_short')}", to_number(data["total_deductible"])],
        is_total=True,
    )
    row = data_row(
        ws, row, [t("common.taxable_estimate"), to_number(data["taxable_estimate"])], is_grand=True
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
