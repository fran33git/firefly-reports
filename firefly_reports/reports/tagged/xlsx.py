"""Excel sheet of the tagged report."""

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font
from openpyxl.utils import get_column_letter

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
    LIGHT_HEX,
    thin,
)

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────


def write_sheet(wb: Workbook, data: dict[str, Any]) -> None:
    tag_label = ", ".join(data["tags"])
    sheet_name = safe_sheet_name(f"Tag {tag_label}" if tag_label else t("excel.sheet_tagged"))
    ws = wb.create_sheet(sheet_name)
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]

    row = title_block(
        ws, t("titles.tagged_transactions").format(tag_label=tag_label), data["owner"], period
    )

    logic = t("pdf.tagged_all_logic") if data["match_all"] else t("pdf.tagged_any_logic")
    ws.merge_cells(f"A{row}:H{row}")
    ws.cell(
        row=row,
        column=1,
        value=f"{t('common.note')}: {logic}: {tag_label}   ·   {t('pdf.total_transactions').format(count=data['total_transactions'])}",
    ).font = Font(name="Calibri", size=9, color=LIGHT_HEX, italic=True)
    ws.row_dimensions[row].height = 16
    row += 2

    # ── Transaction list
    ws.cell(row=row, column=1, value=t("excel.sheet_register").upper()).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 20
    row += 1

    headers = [
        t("common.date"),
        t("common.description"),
        t("common.type"),
        t("common.category"),
        t("common.budget"),
        "Tag",
        f"{t('common.amount')} ({sym})",
        f"{t('common.running_balance')} ({sym})",
    ]
    col_widths = [12, 38, 10, 22, 22, 16, 18]
    row = header_row(ws, row, headers, col_widths=col_widths)

    flat_rows = flatten_rows(data["rows"])
    for r in flat_rows:
        vals = [
            r["date"],
            r["description"],
            r["type"][:3].upper(),
            r["budget"] or "—",
            r["tags"] or "—",
            to_number(r["amount"]),
            to_number(r["running_balance"]),
        ]

        for col_idx, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col_idx, value=val)
            c.font = Font(name="Calibri", size=9.5)
            c.alignment = Alignment(
                horizontal="right" if col_idx in [7, 8] else "left", vertical="center"
            )
            if col_idx in [7, 8]:
                c.number_format = "#,##0.00"
            c.border = Border(bottom=thin("EEEEEE"))
        ws.row_dimensions[row].height = 16
        row += 1

    row = data_row(
        ws,
        row,
        ["", t("excel.total_net_filtered"), "", "", "", "", to_number(data["net"]), ""],
        is_grand=True,
    )
    row += 1

    # ── Category breakdown — Income
    if data["income_by_cat"]:
        ws.cell(row=row, column=1, value=t("pdf.section_income_cat").upper()).font = Font(
            name="Calibri", bold=True, size=9, color=LIGHT_HEX
        )
        ws.row_dimensions[row].height = 20
        row += 1
        row = header_row(
            ws,
            row,
            [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")],
        )
        for r_cat in data["income_by_cat"]:
            row = data_row(
                ws,
                row,
                [r_cat["category"], to_number(r_cat["amount"]), float(r_cat["pct"])],
                indent_col=1,
            )
        row = data_row(
            ws, row, [t("common.total_income"), to_number(data["total_in"]), 100.0], is_total=True
        )
        row += 1

    # ── Category breakdown — Expenses
    if data["expense_by_cat"]:
        ws.cell(row=row, column=1, value=t("pdf.section_expense_cat").upper()).font = Font(
            name="Calibri", bold=True, size=9, color=LIGHT_HEX
        )
        ws.row_dimensions[row].height = 20
        row += 1
        row = header_row(
            ws,
            row,
            [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")],
        )
        for r_cat in data["expense_by_cat"]:
            row = data_row(
                ws,
                row,
                [r_cat["category"], to_number(r_cat["amount"]), float(r_cat["pct"])],
                indent_col=1,
            )
        row = data_row(
            ws, row, [t("common.total_expense"), to_number(data["total_out"]), 100.0], is_total=True
        )
        row += 1

    # ── Grand total row
    row = data_row(ws, row, [t("common.income"), to_number(data["total_in"])], is_total=True)
    row = data_row(ws, row, [t("common.expense"), to_number(data["total_out"])], is_total=True)
    row = data_row(ws, row, [t("common.net"), to_number(data["net"])], is_grand=True)

    ws.auto_filter.ref = (
        f"A{row - data['total_transactions'] - 10}:{get_column_letter(len(headers))}{row - 1}"
    )
    ws.freeze_panes = "A8"
    ws.sheet_view.showGridLines = False
