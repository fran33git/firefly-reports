"""Excel report renderers using openpyxl.

render_all_xlsx() generates 3 sheets (used by earlier main.py versions).
render_all_xlsx_full() generates 16 core sheets and is the current entry point.
"""

from datetime import date as dt_date
from datetime import datetime
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from firefly_reports import i18n
from firefly_reports.i18n import T, t

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────
BLACK_HEX = "000000"
DARK_HEX = "1A1A1A"
MID_HEX = "4A4A4A"
LIGHT_HEX = "888888"
TOTAL_BG = "F2F2F2"  # very light grey for total rows
HEADER_BG = "FFFFFF"  # column header: white with bottom border
WHITE_HEX = "FFFFFF"
RULE_HEX = "CCCCCC"

PCT_FMT = '0.0"%"'


def _thin(color=RULE_HEX) -> Side:
    return Side(border_style="thin", color=color)


def _medium(color=DARK_HEX) -> Side:
    return Side(border_style="medium", color=color)


def _bottom_rule(color=RULE_HEX) -> Border:
    return Border(bottom=_thin(color))


def _top_bottom(top_color=DARK_HEX, bot_color=DARK_HEX) -> Border:
    return Border(top=_medium(top_color), bottom=_thin(bot_color))


def _grand_border() -> Border:
    return Border(top=_medium(), bottom=_medium())


def _body_font(bold=False, size=10, color=DARK_HEX) -> Font:
    return Font(name="Calibri", bold=bold, size=size, color=color)


def _total_bg() -> PatternFill:
    return PatternFill("solid", fgColor=TOTAL_BG)


def _flatten_rows(grouped_rows: list[dict]) -> list[dict]:
    """Helper to flatten grouped transactions for legacy/Excel renderers."""
    flat = []
    for group in grouped_rows:
        splits = group.get("splits", [])
        if not splits:
            flat.append(group)
            continue
        for split in splits:
            item = split.copy()
            item["date"] = group.get("date")
            item["description"] = group.get("description")
            item["type"] = group.get("type", "Standard")
            item["running_balance"] = group.get("running_balance", Decimal("0"))
            flat.append(item)
    return flat


def _fmt_d(v: Decimal) -> float:
    return float(v)


def _safe_sheet_name(name: str, max_len: int = 31) -> str:
    """Remove characters forbidden in Excel sheet names: [ ] * ? / \\ :"""
    for ch in r"[]*?/\\:":
        name = name.replace(ch, "")
    return name[:max_len].strip() or "Sheet"


def _fmt_date(d: Any) -> str:
    """Locale-aware date format: DD/MM/YYYY for Italian, ISO YYYY-MM-DD otherwise."""
    if not hasattr(d, "strftime"):
        return str(d)
    fmt = "%d/%m/%Y" if i18n.CURRENT_LANG == "it" else "%Y-%m-%d"
    return str(d.strftime(fmt))


def _period_str(start: dt_date, end: dt_date) -> str:
    months: dict = T.get("months", {})
    if start.year == end.year and start.month == end.month:
        month_label = months.get(f"{start.month:02d}", str(start.month))
        return f"{month_label.lower()} {start.year}"
    return f"{_fmt_date(start)} – {_fmt_date(end)}"


# ─────────────────────────────────────────────────
# Sheet title block
# ─────────────────────────────────────────────────
def _title_block(ws, sheet_title: str, owner: str, period: str) -> int:
    """
    Write the first 4 header rows.
    Returns the row number from which content should start.
    """
    ws.row_dimensions[1].height = 28
    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = sheet_title.upper()
    c.font = Font(name="Calibri", bold=True, size=14, color=DARK_HEX)
    c.alignment = Alignment(horizontal="left", vertical="center")
    c.border = Border(bottom=_thin())

    ws.row_dimensions[2].height = 16
    ws.merge_cells("A2:H2")
    c2 = ws["A2"]
    c2.value = owner
    c2.font = Font(name="Calibri", size=10, color=MID_HEX)
    c2.alignment = Alignment(horizontal="left", vertical="center")

    ws.row_dimensions[3].height = 14
    ws.merge_cells("A3:H3")
    c3 = ws["A3"]
    c3.value = t("excel.header_period_ref").format(period=period, date=_fmt_date(datetime.now()))
    c3.font = Font(name="Calibri", size=9, color=LIGHT_HEX, italic=True)
    c3.alignment = Alignment(horizontal="left", vertical="center")
    c3.border = Border(bottom=_medium())

    ws.row_dimensions[4].height = 8  # spacer row

    return 5  # first content row


def _col_header_row(ws, row: int, labels: list, col_widths: list | None = None):
    """Write a column header row with bold font and thin bottom border."""
    for col_idx, label in enumerate(labels, start=1):
        c = ws.cell(row=row, column=col_idx, value=label)
        c.font = _body_font(bold=True, size=9.5)
        c.alignment = Alignment(horizontal="right" if col_idx > 1 else "left", vertical="center")
        c.border = Border(bottom=_thin(DARK_HEX))
    if col_widths:
        for i, w in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 20
    return row + 1


def _data_row(
    ws,
    row: int,
    values: list,
    indent_col: int | None = None,
    is_total: bool = False,
    is_grand: bool = False,
):
    """
    Write a data row.
    - is_total: bold + grey background + thin top border
    - is_grand: larger bold + thick top/bottom border
    """
    font_size = 10.5 if is_grand else 10
    bold = is_total or is_grand

    for col_idx, val in enumerate(values, start=1):
        c = ws.cell(row=row, column=col_idx, value=val)
        c.font = _body_font(bold=bold, size=font_size)
        is_num = isinstance(val, (int, float)) and col_idx > 1
        c.alignment = Alignment(
            horizontal="right" if (is_num or col_idx > 1) else "left",
            vertical="center",
            indent=1
            if (indent_col and col_idx == indent_col and not is_total and not is_grand)
            else 0,
        )
        if is_num:
            c.number_format = "#,##0.00"
        if is_total:
            c.fill = _total_bg()
            if col_idx == 1:
                c.border = Border(top=_thin(RULE_HEX), bottom=_thin(RULE_HEX))
            else:
                c.border = Border(top=_thin(RULE_HEX), bottom=_thin(RULE_HEX))
        if is_grand:
            c.fill = _total_bg()
            c.border = _grand_border()

    ws.row_dimensions[row].height = 18 if not is_grand else 22
    return row + 1


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────
def _build_cash_flow_sheet(wb: Workbook, data: dict):
    ws = wb.create_sheet(t("excel.sheet_cashflow"))
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]

    row = _title_block(ws, t("excel.sheet_cashflow"), data["owner"], period)

    # ── Income
    ws.merge_cells(f"A{row}:H{row}")
    c = ws.cell(row=row, column=1, value=t("excel.section_inflows"))
    c.font = Font(name="Calibri", bold=True, size=9, color=LIGHT_HEX)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 22
    row += 1

    row = _col_header_row(
        ws, row, [t("common.category_item"), f"{t('common.amount')} ({sym})"], col_widths=[42, 18]
    )
    for item in data["inflows"]:
        row = _data_row(ws, row, [item["category"], _fmt_d(item["amount"])], indent_col=1)
    row = _data_row(ws, row, [t("common.total_income"), _fmt_d(data["total_in"])], is_total=True)

    row += 1  # spacer row

    # ── Expenses
    ws.merge_cells(f"A{row}:H{row}")
    c = ws.cell(row=row, column=1, value=t("excel.section_outflows"))
    c.font = Font(name="Calibri", bold=True, size=9, color=LIGHT_HEX)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 22
    row += 1

    row = _col_header_row(ws, row, [t("common.category_item"), f"{t('common.amount')} ({sym})"])
    for item in data["outflows"]:
        row = _data_row(ws, row, [item["category"], _fmt_d(item["amount"])], indent_col=1)
    row = _data_row(ws, row, [t("common.total_expense"), _fmt_d(data["total_out"])], is_total=True)

    row += 1

    # ── Monthly
    if len(data["by_month"]) > 1:
        months_it = T.get("months", {})
        ws.merge_cells(f"A{row}:H{row}")
        c = ws.cell(row=row, column=1, value=t("excel.section_monthly"))
        c.font = Font(name="Calibri", bold=True, size=9, color=LIGHT_HEX)
        ws.row_dimensions[row].height = 22
        row += 1

        row = _col_header_row(
            ws,
            row,
            [
                t("common.month"),
                f"{t('common.income')} ({sym})",
                f"{t('common.expense')} ({sym})",
                f"{t('common.net_flow')} ({sym})",
            ],
            col_widths=[22, 18, 18, 20],
        )
        for mk, vals in data["by_month"].items():
            y, m = mk.split("-")
            row = _data_row(
                ws,
                row,
                [
                    f"{months_it.get(m, m)} {y}",
                    _fmt_d(vals["in"]),
                    _fmt_d(vals["out"]),
                    _fmt_d(vals["net"]),
                ],
            )
        row += 1

    # ── Grand total row
    row = _data_row(ws, row, [t("common.net_flow"), _fmt_d(data["net"])], is_grand=True)

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Sheet 2 — Income & Expense Summary
# ─────────────────────────────────────────────────
def _build_income_expense_sheet(wb: Workbook, data: dict):
    ws = wb.create_sheet(t("excel.sheet_income"))
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]

    row = _title_block(ws, t("excel.sheet_income"), data["owner"], period)

    # Income
    ws.merge_cells(f"A{row}:H{row}")
    ws.cell(row=row, column=1, value=t("pdf.section_income_cat")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 22
    row += 1

    row = _col_header_row(
        ws,
        row,
        [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")],
        col_widths=[40, 18, 16],
    )
    for r in data["income_rows"]:
        row = _data_row(
            ws, row, [r["category"], _fmt_d(r["amount"]), float(r["pct"])], indent_col=1
        )
    row = _data_row(
        ws, row, [t("common.total_income"), _fmt_d(data["total_income"]), 100.0], is_total=True
    )
    ws.cell(row=row - 1, column=3).number_format = '0.0"%"'

    row += 1

    # Expenses
    ws.merge_cells(f"A{row}:H{row}")
    ws.cell(row=row, column=1, value=t("pdf.section_expense_cat")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 22
    row += 1

    row = _col_header_row(
        ws, row, [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")]
    )
    for r in data["expense_rows"]:
        row = _data_row(
            ws, row, [r["category"], _fmt_d(r["amount"]), float(r["pct"])], indent_col=1
        )
    row = _data_row(
        ws, row, [t("common.total_expense"), _fmt_d(data["total_expense"]), 100.0], is_total=True
    )

    row += 1

    # Budget
    if data["budget_breakdown"]:
        ws.merge_cells(f"A{row}:H{row}")
        ws.cell(row=row, column=1, value=t("pdf.section_summary_analysis")).font = Font(
            name="Calibri", bold=True, size=9, color=LIGHT_HEX
        )
        ws.row_dimensions[row].height = 22
        row += 1
        row = _col_header_row(ws, row, [t("common.budget"), f"{t('common.amount')} ({sym})"])
        for b in data["budget_breakdown"]:
            row = _data_row(ws, row, [b["budget"], _fmt_d(b["spent"])], indent_col=1)
        row += 1

    # Grand total
    row = _data_row(
        ws,
        row,
        [t("common.net_savings"), _fmt_d(data["net_savings"]), float(data["savings_rate"])],
        is_grand=True,
    )
    ws.cell(row=row - 1, column=3).number_format = '0.0"%"'

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Sheet 3 — Transaction Register
# ─────────────────────────────────────────────────
def _build_transaction_register_sheet(wb: Workbook, data: dict):
    ws = wb.create_sheet(t("excel.sheet_register"))
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]

    row = _title_block(ws, t("excel.sheet_register"), data["owner"], period)

    headers = [
        t("common.date"),
        t("common.description"),
        t("common.type"),
        t("common.category"),
        t("common.budget"),
        f"{t('common.amount')} ({sym})",
        f"{t('common.running_balance')} ({sym})",
    ]
    col_widths = [12, 38, 12, 22, 18, 16, 18]
    row = _col_header_row(ws, row, headers, col_widths=col_widths)

    current_month = None
    months_it = T.get("months", {})

    flat_rows = _flatten_rows(data["rows"])
    for r in flat_rows:
        mk = r["date"][:7]
        if mk != current_month:
            current_month = mk
            y, m = mk.split("-")
            # month separator row
            ws.merge_cells(f"A{row}:G{row}")
            c = ws.cell(row=row, column=1, value=f"{months_it.get(m, m)} {y}".upper())
            c.font = Font(name="Calibri", bold=True, size=8.5, color=LIGHT_HEX)
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.border = Border(bottom=_thin())
            ws.row_dimensions[row].height = 16
            row += 1

        vals = [
            r["date"],
            r["description"],
            r["type"][:3].upper(),
            r["category"] or "—",
            r["budget"] or "—",
            _fmt_d(r["amount"]),
            _fmt_d(r["running_balance"]),
        ]
        for col_idx, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col_idx, value=val)
            c.font = Font(name="Calibri", size=9.5)
            is_num = col_idx in [6, 7]
            c.alignment = Alignment(horizontal="right" if is_num else "left", vertical="center")
            if is_num:
                c.number_format = "#,##0.00"
            c.border = Border(bottom=_thin("EEEEEE"))
        ws.row_dimensions[row].height = 16
        row += 1

    # Final balance row
    if data["rows"]:
        final_bal = _fmt_d(data["rows"][-1]["running_balance"])
        row = _data_row(
            ws, row, ["", t("pdf.closing_balance_period"), "", "", "", "", final_bal], is_grand=True
        )

    ws.auto_filter.ref = f"A{row - len(data['rows']) - 2}:G{row - 1}"
    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────
def render_all_xlsx(
    cf: dict[str, Any], ie: dict[str, Any], reg: dict[str, Any], output_path: str
) -> None:
    """Write a 3-sheet summary workbook (cash flow, income/expense, register)."""
    wb = Workbook()
    wb.remove(wb.active)
    _build_cash_flow_sheet(wb, cf)
    _build_income_expense_sheet(wb, ie)
    _build_transaction_register_sheet(wb, reg)
    wb.save(output_path)


# ─────────────────────────────────────────────────
# Sheet 4 — Asset & Net Worth Statement
# ─────────────────────────────────────────────────
def _build_net_worth_sheet(wb: Workbook, data: dict):
    ws = wb.create_sheet(t("excel.sheet_net_worth"))
    as_of = _fmt_date(data["as_of_date"])
    row = _title_block(
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

        row = _col_header_row(
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
            row = _data_row(
                ws,
                row,
                [acc["name"], acc["iban_masked"], acc["currency_code"], _fmt_d(acc["balance"])],
                indent_col=1,
            )

        row = _data_row(
            ws,
            row,
            [t("pdf.subtotal").format(role=group["role_label"]), "", "", _fmt_d(group["subtotal"])],
            is_total=True,
        )
        row += 1

    row = _data_row(
        ws,
        row,
        [t("excel.total_assets_short"), "", "", _fmt_d(data["total_assets"])],
        is_total=True,
    )
    row = _data_row(
        ws,
        row,
        [t("excel.total_liabilities_short"), "", "", _fmt_d(data["total_liabilities"])],
        is_total=True,
    )
    row = _data_row(
        ws, row, [t("common.net_worth"), "", "", _fmt_d(data["net_worth"])], is_grand=True
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Sheet 5 — Account Statements (one sheet per account)
# ─────────────────────────────────────────────────
def _build_account_statement_sheets(wb: Workbook, statements: list):
    for stmt in statements:
        sheet_name = _safe_sheet_name(f"{t('common.account')} {stmt['account_name']}")
        ws = wb.create_sheet(sheet_name)
        period = _period_str(stmt["period_start"], stmt["period_end"])
        sym = stmt["currency"]

        row = _title_block(
            ws, f"{t('common.account')} {stmt['account_name']}", stmt["owner"], period
        )

        # Account metadata
        ws.cell(row=row, column=1, value="IBAN").font = _body_font(bold=True, size=9)
        ws.cell(row=row, column=2, value=stmt["account_iban"]).font = _body_font(size=9)
        ws.row_dimensions[row].height = 16
        row += 1
        ws.cell(row=row, column=1, value=t("common.opening_balance")).font = _body_font(
            bold=True, size=9
        )
        ws.cell(row=row, column=2, value=_fmt_d(stmt["opening_balance"])).number_format = "#,##0.00"
        ws.cell(row=row, column=2).font = _body_font(size=9)
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
        row = _col_header_row(ws, row, headers, col_widths=col_widths)

        flat_stmt_rows = _flatten_rows(stmt["rows"])
        for r in flat_stmt_rows:
            vals = [
                r["date"],
                r["description"],
                r["type"][:3].upper(),
                r["counterpart"] or "—",
                r["category"] or "—",
                _fmt_d(r["amount"]),
                _fmt_d(r["running_balance"]),
            ]
            for col_idx, val in enumerate(vals, start=1):
                c = ws.cell(row=row, column=col_idx, value=val)
                c.font = Font(name="Calibri", size=9.5)
                c.alignment = Alignment(
                    horizontal="right" if col_idx in [6, 7] else "left", vertical="center"
                )
                if col_idx in [6, 7]:
                    c.number_format = "#,##0.00"
                c.border = Border(bottom=_thin("EEEEEE"))
            ws.row_dimensions[row].height = 16
            row += 1

        row = _data_row(
            ws,
            row,
            ["", t("excel.closing_balance_short"), "", "", "", "", _fmt_d(stmt["closing_balance"])],
            is_grand=True,
        )

        ws.freeze_panes = "A8"
        ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Sheet 6 — Annual Tax Summary
# ─────────────────────────────────────────────────
def _build_tax_summary_sheet(wb: Workbook, data: dict):
    ws = wb.create_sheet(t("excel.sheet_tax"))
    sym = data["currency"]
    row = _title_block(
        ws, t("titles.tax_summary"), data["owner"], t("pdf.fiscal_year").format(year=data["year"])
    )

    # Income by category
    ws.cell(row=row, column=1, value=t("pdf.section_tax_income")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 20
    row += 1
    row = _col_header_row(
        ws,
        row,
        [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")],
        col_widths=[38, 18, 14],
    )
    for r in data["income_by_cat"]:
        row = _data_row(
            ws,
            row,
            [
                r["category"],
                _fmt_d(r["amount"]),
                float((r["amount"] / data["total_income"] * 100).quantize(Decimal("0.1")))
                if data["total_income"]
                else 0.0,
            ],
            indent_col=1,
        )
    row = _data_row(
        ws,
        row,
        [t("excel.total_income_section"), _fmt_d(data["total_income"]), 100.0],
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
    row = _col_header_row(ws, row, [t("common.income_client"), f"{t('common.amount')} ({sym})"])
    for r in data["income_by_client"]:
        row = _data_row(ws, row, [r["client"], _fmt_d(r["amount"])], indent_col=1)
    row += 1

    # Deductible expenses
    ws.cell(row=row, column=1, value=t("pdf.section_tax_deductible")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 20
    row += 1
    row = _col_header_row(ws, row, [t("common.category"), f"{t('common.amount')} ({sym})"])
    for r in data["deductible_rows"]:
        row = _data_row(ws, row, [r["category"], _fmt_d(r["amount"])], indent_col=1)
    row = _data_row(
        ws,
        row,
        [t("excel.total_deductible_short"), _fmt_d(data["total_deductible"])],
        is_total=True,
    )
    row += 1

    # Tax summary
    row = _data_row(
        ws, row, [t("excel.total_income_section"), _fmt_d(data["total_income"])], is_total=True
    )
    row = _data_row(
        ws,
        row,
        [f"- {t('excel.total_deductible_short')}", _fmt_d(data["total_deductible"])],
        is_total=True,
    )
    row = _data_row(
        ws, row, [t("common.taxable_estimate"), _fmt_d(data["taxable_estimate"])], is_grand=True
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Sheet 7 — Expense Trend by Category
# ─────────────────────────────────────────────────
def _build_expense_trend_sheet(wb: Workbook, data: dict):
    ws = wb.create_sheet(t("excel.sheet_expense_trend"))
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    months = data["months"]

    row = _title_block(ws, t("titles.expense_trend"), data["owner"], period)

    months_abbr = T.get("months_abbr", {})

    def _mk(mk):
        y, m = mk.split("-")
        return f"{months_abbr.get(m, m)} {y[-2:]}"

    headers = [t("common.category")] + [_mk(m) for m in months] + [f"{t('common.total')} ({sym})"]
    col_widths = [32] + [11] * len(months) + [16]
    row = _col_header_row(ws, row, headers, col_widths=col_widths)

    for r in data["rows"]:
        vals = (
            [r["category"]]
            + [_fmt_d(v) if v > 0 else None for v in r["monthly"]]
            + [_fmt_d(r["total"])]
        )
        for col_idx, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col_idx, value=val)
            c.font = Font(name="Calibri", size=9.5)
            c.alignment = Alignment(
                horizontal="right" if col_idx > 1 else "left", vertical="center"
            )
            if val is not None and col_idx > 1:
                c.number_format = "#,##0.00"
            c.border = Border(bottom=_thin("EEEEEE"))
        ws.row_dimensions[row].height = 16
        row += 1

    # Expense total row
    tot_vals = (
        [t("excel.total_expense_matrix")]
        + [_fmt_d(v) for v in data["totals_by_month"]]
        + [_fmt_d(data["grand_total"])]
    )
    row = _data_row(ws, row, tot_vals, is_total=True)

    # Income comparison row
    inc_vals = (
        [t("excel.income_for_comparison")]
        + [_fmt_d(v) for v in data["income_by_month"]]
        + [_fmt_d(sum(data["income_by_month"]))]
    )
    for col_idx, val in enumerate(inc_vals, start=1):
        c = ws.cell(row=row, column=col_idx, value=val)
        c.font = Font(name="Calibri", size=9.5, italic=True, color=MID_HEX)
        c.alignment = Alignment(horizontal="right" if col_idx > 1 else "left", vertical="center")
        if col_idx > 1 and isinstance(val, float):
            c.number_format = "#,##0.00"
        c.border = Border(top=_thin())
    ws.row_dimensions[row].height = 18

    ws.freeze_panes = f"B{row - len(data['rows']) - 3}"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Extended entry point (first 7 reports)
# ─────────────────────────────────────────────────
def render_all_xlsx_extended(
    cf: dict[str, Any],
    ie: dict[str, Any],
    reg: dict[str, Any],
    net_worth: dict[str, Any],
    statements: list[dict[str, Any]],
    tax: dict[str, Any],
    trend: dict[str, Any],
    output_path: str,
) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    _build_cash_flow_sheet(wb, cf)
    _build_income_expense_sheet(wb, ie)
    _build_transaction_register_sheet(wb, reg)
    _build_net_worth_sheet(wb, net_worth)
    _build_account_statement_sheets(wb, statements)
    _build_tax_summary_sheet(wb, tax)
    _build_expense_trend_sheet(wb, trend)
    wb.save(output_path)


# ─────────────────────────────────────────────────
# Sheet 8 — Tagged Transactions Report
# ─────────────────────────────────────────────────
def _build_tagged_sheet(wb: Workbook, data: dict):
    tag_label = ", ".join(data["tags"])
    sheet_name = _safe_sheet_name(f"Tag {tag_label}" if tag_label else t("excel.sheet_tagged"))
    ws = wb.create_sheet(sheet_name)
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]

    row = _title_block(
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
    row = _col_header_row(ws, row, headers, col_widths=col_widths)

    flat_rows = _flatten_rows(data["rows"])
    for r in flat_rows:
        vals = [
            r["date"],
            r["description"],
            r["type"][:3].upper(),
            r["budget"] or "—",
            r["tags"] or "—",
            _fmt_d(r["amount"]),
            _fmt_d(r["running_balance"]),
        ]

        for col_idx, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col_idx, value=val)
            c.font = Font(name="Calibri", size=9.5)
            c.alignment = Alignment(
                horizontal="right" if col_idx in [7, 8] else "left", vertical="center"
            )
            if col_idx in [7, 8]:
                c.number_format = "#,##0.00"
            c.border = Border(bottom=_thin("EEEEEE"))
        ws.row_dimensions[row].height = 16
        row += 1

    row = _data_row(
        ws,
        row,
        ["", t("excel.total_net_filtered"), "", "", "", "", _fmt_d(data["net"]), ""],
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
        row = _col_header_row(
            ws,
            row,
            [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")],
        )
        for r_cat in data["income_by_cat"]:
            row = _data_row(
                ws,
                row,
                [r_cat["category"], _fmt_d(r_cat["amount"]), float(r_cat["pct"])],
                indent_col=1,
            )
        row = _data_row(
            ws, row, [t("common.total_income"), _fmt_d(data["total_in"]), 100.0], is_total=True
        )
        row += 1

    # ── Category breakdown — Expenses
    if data["expense_by_cat"]:
        ws.cell(row=row, column=1, value=t("pdf.section_expense_cat").upper()).font = Font(
            name="Calibri", bold=True, size=9, color=LIGHT_HEX
        )
        ws.row_dimensions[row].height = 20
        row += 1
        row = _col_header_row(
            ws,
            row,
            [t("common.category"), f"{t('common.amount')} ({sym})", t("excel.col_share_pct")],
        )
        for r_cat in data["expense_by_cat"]:
            row = _data_row(
                ws,
                row,
                [r_cat["category"], _fmt_d(r_cat["amount"]), float(r_cat["pct"])],
                indent_col=1,
            )
        row = _data_row(
            ws, row, [t("common.total_expense"), _fmt_d(data["total_out"]), 100.0], is_total=True
        )
        row += 1

    # ── Grand total row
    row = _data_row(ws, row, [t("common.income"), _fmt_d(data["total_in"])], is_total=True)
    row = _data_row(ws, row, [t("common.expense"), _fmt_d(data["total_out"])], is_total=True)
    row = _data_row(ws, row, [t("common.net"), _fmt_d(data["net"])], is_grand=True)

    ws.auto_filter.ref = (
        f"A{row - data['total_transactions'] - 10}:{get_column_letter(len(headers))}{row - 1}"
    )
    ws.freeze_panes = "A8"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Report 9 — Budget vs. Actual
# ─────────────────────────────────────────────────
def _build_budget_vs_actual_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_budget"))
    period = _period_str(data["period_start"], data["period_end"])
    row = _title_block(ws, t("titles.budget_vs_actual_report"), data["owner"], period)
    sym = data["currency"]

    row = _col_header_row(
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
        row = _data_row(
            ws,
            row,
            [
                r["budget_name"],
                _fmt_d(r["limit"]),
                _fmt_d(r["actual"]),
                var,
                float(r["variance_pct"]) / 100,
            ],
        )
        ws.cell(row=row - 1, column=5).number_format = "0.0%"

    row = _data_row(
        ws,
        row,
        [
            t("pdf.budgeted_total"),
            _fmt_d(data["total_limit"]),
            _fmt_d(data["total_actual"]),
            _fmt_d(data["total_variance"]),
            "",
        ],
        is_total=True,
    )

    if data["unbudgeted_spending"] > 0:
        row += 1
        row = _data_row(
            ws, row, [t("excel.unbudgeted"), _fmt_d(data["unbudgeted_spending"])], is_total=True
        )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Report 10 — Bills & Subscriptions
# ─────────────────────────────────────────────────
def _build_bills_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_bills"))
    period = _period_str(data["period_start"], data["period_end"])
    row = _title_block(ws, t("titles.bills"), data["owner"], period)
    sym = data["currency"]

    row = _col_header_row(
        ws,
        row,
        [
            t("common.name"),
            t("common.frequency"),
            t("excel.col_bills_expected").format(sym=sym),
            f"{t('common.paid')} ({sym})",
            t("excel.col_bills_count"),
            t("excel.col_bills_last"),
        ],
        col_widths=[28, 14, 16, 16, 14, 16],
    )

    for r in data["rows"]:
        row = _data_row(
            ws,
            row,
            [
                r["name"],
                r["frequency"],
                _fmt_d(r["expected"]),
                _fmt_d(r["paid_amount"]),
                r["times_paid"],
                r["last_paid"] or "—",
            ],
        )

    row = _data_row(
        ws,
        row,
        [t("common.total"), "", _fmt_d(data["total_expected"]), _fmt_d(data["total_paid"]), "", ""],
        is_total=True,
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Report 11 — Savings Goals
# ─────────────────────────────────────────────────
def _build_savings_goals_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_savings"))
    as_of = _fmt_date(data["as_of_date"])
    row = _title_block(
        ws, t("titles.savings_goals"), data["owner"], t("pdf.as_of").format(date=as_of)
    )
    sym = data["currency"]

    row = _col_header_row(
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
        row = _data_row(
            ws,
            row,
            [
                g["name"],
                _fmt_d(g["target"]),
                _fmt_d(g["current"]),
                _fmt_d(g["remaining"]),
                float(g["pct"]) / 100,
                g["target_date"] or "—",
                _fmt_d(g["monthly_needed"]) if g["monthly_needed"] > 0 else None,
            ],
        )
        ws.cell(row=row - 1, column=5).number_format = "0.0%"

    row = _data_row(
        ws,
        row,
        [
            t("common.total"),
            _fmt_d(data["total_target"]),
            _fmt_d(data["total_saved"]),
            _fmt_d(data["total_target"] - data["total_saved"]),
            float(data["overall_pct"]) / 100,
            "",
            "",
        ],
        is_total=True,
    )
    ws.cell(row=row - 1, column=5).number_format = "0.0%"

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Report 12 — Liabilities & Debt
# ─────────────────────────────────────────────────
def _build_liabilities_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_liabilities"))
    as_of = _fmt_date(data["as_of_date"])
    row = _title_block(
        ws, t("titles.liabilities"), data["owner"], t("pdf.as_of").format(date=as_of)
    )
    sym = data["currency"]

    row = _col_header_row(
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
        row = _data_row(
            ws,
            row,
            [
                r["name"],
                r["type"],
                _fmt_d(r["debt_amount"]),
                float(r["interest_rate"]) if r["interest_rate"] else None,
                r["currency_code"],
                _fmt_d(r["period_payments"]) if r["period_payments"] else None,
            ],
        )

    row = _data_row(
        ws,
        row,
        [
            t("common.total_liabilities"),
            "",
            _fmt_d(data["total_debt"]),
            "",
            "",
            _fmt_d(data["total_payments"]),
        ],
        is_grand=True,
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Report 13 — KPI Scorecard
# ─────────────────────────────────────────────────
def _build_kpi_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_kpi"))
    period = _period_str(data["period_start"], data["period_end"])
    row = _title_block(ws, t("titles.kpi_scorecard"), data["owner"], period)
    sym = data["currency"]

    row = _col_header_row(
        ws,
        row,
        [t("excel.kpi_indicator"), t("excel.kpi_value"), t("common.note")],
        col_widths=[36, 20, 40],
    )

    kpis = [
        (t("excel.kpi_savings_rate"), f"{data['savings_rate']} %", t("excel.kpi_savings_note")),
        (t("pdf.kpi_burn_rate"), _fmt_d(data["burn_rate"]), t("pdf.kpi_burn_rate_note")),
        (
            t("excel.kpi_runway"),
            f"{data['cash_runway']} {t('pdf.kpi_runway_unit')}",
            t("excel.kpi_runway_note"),
        ),
        (t("pdf.kpi_net_worth"), _fmt_d(data["net_worth"]), t("pdf.kpi_net_worth_note")),
        (
            t("excel.kpi_liquidity"),
            f"{data['liquidity_ratio']:.2f}x" if data["liquidity_ratio"] else "N/D",
            "Liquid Assets / Total Liabilities",
        ),
        (
            t("pdf.kpi_net_cash_flow"),
            _fmt_d(data["net_cash_flow"]),
            t("pdf.kpi_net_cash_flow_note"),
        ),
        (
            t("pdf.kpi_avg_monthly_in"),
            _fmt_d(data["avg_monthly_in"]),
            t("pdf.kpi_months_note").format(n_months=data["n_months"]),
        ),
        (
            t("pdf.kpi_avg_monthly_out"),
            _fmt_d(data["avg_monthly_out"]),
            t("pdf.kpi_months_note").format(n_months=data["n_months"]),
        ),
        (t("pdf.kpi_hhi"), float(data["hhi"]), t("pdf.kpi_hhi_note")),
        (
            t("pdf.kpi_top_client"),
            f"{data['top1_client']} ({data['top1_pct']} %)",
            t("pdf.kpi_top_client_note"),
        ),
    ]
    for label, val, note in kpis:
        for col_idx, v in enumerate([label, val, note], start=1):
            c = ws.cell(row=row, column=col_idx, value=v)
            c.font = Font(name="Calibri", size=10)
            c.alignment = Alignment(
                horizontal="left" if col_idx != 2 else "right", vertical="center"
            )
            if col_idx == 2 and isinstance(v, float):
                c.number_format = "#,##0.00"
            c.border = Border(bottom=_thin("EEEEEE"))
        ws.row_dimensions[row].height = 18
        row += 1

    row += 1
    ws.cell(row=row, column=1, value=t("pdf.trend_monthly")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 20
    row += 1

    months_abbr = T.get("months_abbr", {})

    row = _col_header_row(
        ws,
        row,
        [
            t("common.month"),
            f"{t('common.income')} ({sym})",
            f"{t('common.expense')} ({sym})",
            f"{t('common.net')} ({sym})",
            t("common.variation") + " %",
        ],
    )
    prev_net = None
    for m in data["monthly_trend"]:
        y, mo = m["month"].split("-")
        var_pct = None
        if prev_net and prev_net != 0:
            var_pct = float((m["net"] - prev_net) / abs(prev_net) * 100)
        prev_net = m["net"]
        row = _data_row(
            ws,
            row,
            [
                f"{months_abbr.get(mo, mo)} {y}",
                _fmt_d(m["income"]),
                _fmt_d(m["expense"]),
                _fmt_d(m["net"]),
                var_pct,
            ],
        )
        if var_pct is not None:
            ws.cell(row=row - 1, column=5).number_format = "0.0%"

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Report 14 — Year-over-Year
# ─────────────────────────────────────────────────
def _build_yoy_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_yoy"))
    la, lb = data["period_a"]["label"], data["period_b"]["label"]
    row = _title_block(ws, t("titles.yoy_comparison"), data["owner"], f"{lb} vs {la}")
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

        row = _col_header_row(
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
            row = _data_row(
                ws,
                row,
                [
                    r["category"],
                    _fmt_d(r["amount_a"]),
                    _fmt_d(r["amount_b"]),
                    _fmt_d(r["delta"]),
                    dpct,
                ],
                indent_col=1,
            )
            if dpct is not None:
                ws.cell(row=row - 1, column=5).number_format = "0.0%"

        dpct_tot = float((tot_a - tot_b) / tot_b * 100) / 100 if tot_b else None
        row = _data_row(
            ws,
            row,
            [t("common.total"), _fmt_d(tot_a), _fmt_d(tot_b), _fmt_d(tot_a - tot_b), dpct_tot],
            is_total=True,
        )
        if dpct_tot is not None:
            ws.cell(row=row - 1, column=5).number_format = "0.0%"
        row += 1

    row = _data_row(
        ws,
        row,
        [
            t("common.net_flow"),
            _fmt_d(data["net_a"]),
            _fmt_d(data["net_b"]),
            _fmt_d(data["net_a"] - data["net_b"]),
            "",
        ],
        is_grand=True,
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Report 15 — Cumulative Cash Flow
# ─────────────────────────────────────────────────
def _build_cumulative_cf_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_cumulative"))
    period = _period_str(data["period_start"], data["period_end"])
    row = _title_block(ws, t("titles.cumulative_cash_flow"), data["owner"], period)
    sym = data["currency"]

    row = _col_header_row(
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
        row = _data_row(
            ws,
            row,
            [
                m["month_label"],
                _fmt_d(m["income"]),
                _fmt_d(m["expense"]),
                _fmt_d(m["net"]),
                _fmt_d(m["cumulative"]),
            ],
        )

    row = _data_row(
        ws,
        row,
        [t("pdf.cumulative_final"), "", "", "", _fmt_d(data["final_cumulative"])],
        is_grand=True,
    )

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False


# ─────────────────────────────────────────────────
# Report 16 — Income Concentration
# ─────────────────────────────────────────────────
def _build_income_concentration_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_concentration"))
    period = _period_str(data["period_start"], data["period_end"])
    row = _title_block(ws, t("titles.income_concentration"), data["owner"], period)
    sym = data["currency"]

    row = _col_header_row(
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
        row = _data_row(
            ws,
            row,
            [
                r["client"],
                _fmt_d(r["amount"]),
                float(r["pct"]) / 100,
                r["count"],
                _fmt_d(r["avg_per_tx"]),
            ],
            indent_col=1,
        )
        ws.cell(row=row - 1, column=3).number_format = "0.0%"

    row = _data_row(
        ws, row, [t("common.total"), _fmt_d(data["total_income"]), 1.0, "", ""], is_total=True
    )
    ws.cell(row=row - 1, column=3).number_format = "0.0%"


def _build_summary_sheet(wb, data):
    ws = wb.create_sheet(t("excel.sheet_summary"))
    period = _period_str(data["period_start"], data["period_end"])
    row = _title_block(ws, t("titles.summary"), data["owner"], period)

    row = _col_header_row(
        ws,
        row,
        [t("excel.col_summary_item"), t("excel.col_summary_value")],
        col_widths=[34, 24],
    )

    inst = data["instance"]
    counts = data["counts"]
    p = data["period"]

    sections = [
        (
            t("summary.section_instance"),
            [
                (t("summary.firefly_version"), inst["firefly_version"]),
                (t("summary.api_version"), inst["api_version"]),
                (t("summary.server_os"), inst["os"]),
                (t("summary.php_version"), inst["php_version"]),
                (t("summary.user_email"), inst["user_email"]),
                (t("summary.user_role"), inst["user_role"]),
            ],
        ),
        (
            t("summary.section_counts"),
            [
                (t("summary.asset_accounts"), str(counts["asset_accounts"])),
                (t("summary.liabilities"), str(counts["liabilities"])),
                (t("summary.budgets"), str(counts["budgets"])),
                (t("summary.bills"), str(counts["bills"])),
                (t("summary.piggy_banks"), str(counts["piggy_banks"])),
            ],
        ),
        (
            t("summary.section_period"),
            [
                (t("summary.tx_total"), str(p["tx_total"])),
                (t("summary.tx_deposits"), str(p["tx_deposits"])),
                (t("summary.tx_withdrawals"), str(p["tx_withdrawals"])),
                (t("summary.tx_transfers"), str(p["tx_transfers"])),
                (t("summary.first_tx_date"), p["first_tx_date"]),
                (t("summary.last_tx_date"), p["last_tx_date"]),
                (t("summary.accounts_used"), str(p["accounts_used"])),
                (t("summary.categories_used"), str(p["categories_used"])),
                (t("summary.payees_used"), str(p["payees_used"])),
                (t("summary.tags_used"), str(p["tags_used"])),
                (t("summary.avg_daily_income"), _fmt_d(p["avg_daily_income"])),
                (t("summary.avg_daily_expense"), _fmt_d(p["avg_daily_expense"])),
            ],
        ),
    ]

    for section_title, items in sections:
        row = _data_row(ws, row, [section_title.upper(), ""], is_total=True)
        for label, value in items:
            row = _data_row(ws, row, [label, value if value != "" else "—"], indent_col=1)


# ─────────────────────────────────────────────────
# Full entry point — 16 core reports
# ─────────────────────────────────────────────────
def render_all_xlsx_full(reports: dict[str, Any], output_path: str) -> None:
    """Write a workbook covering the core report types.

    Expected keys in reports: cf, ie, reg, net_worth, statements, tax, trend,
    tagged, budget, bills, savings, liabilities, kpi, yoy, cumulative_cf,
    concentration, summary. Sheets whose value is None or missing are skipped (e.g.
    yoy is unavailable in date-range mode).
    """
    wb = Workbook()
    wb.remove(wb.active)

    if reports.get("cf"):
        _build_cash_flow_sheet(wb, reports["cf"])
    if reports.get("ie"):
        _build_income_expense_sheet(wb, reports["ie"])
    if reports.get("reg"):
        _build_transaction_register_sheet(wb, reports["reg"])
    if reports.get("net_worth"):
        _build_net_worth_sheet(wb, reports["net_worth"])
    if reports.get("statements"):
        _build_account_statement_sheets(wb, reports["statements"])
    if reports.get("tax"):
        _build_tax_summary_sheet(wb, reports["tax"])
    if reports.get("trend"):
        _build_expense_trend_sheet(wb, reports["trend"])
    if reports.get("tagged"):
        _build_tagged_sheet(wb, reports["tagged"])
    if reports.get("budget"):
        _build_budget_vs_actual_sheet(wb, reports["budget"])
    if reports.get("bills"):
        _build_bills_sheet(wb, reports["bills"])
    if reports.get("savings"):
        _build_savings_goals_sheet(wb, reports["savings"])
    if reports.get("liabilities"):
        _build_liabilities_sheet(wb, reports["liabilities"])
    if reports.get("kpi"):
        _build_kpi_sheet(wb, reports["kpi"])
    if reports.get("yoy"):
        _build_yoy_sheet(wb, reports["yoy"])
    if reports.get("cumulative_cf"):
        _build_cumulative_cf_sheet(wb, reports["cumulative_cf"])
    if reports.get("concentration"):
        _build_income_concentration_sheet(wb, reports["concentration"])
    if reports.get("summary"):
        _build_summary_sheet(wb, reports["summary"])

    wb.save(output_path)
