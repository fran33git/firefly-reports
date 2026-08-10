"""PDF report renderers using ReportLab Platypus.

Each public render_*_pdf(data, path) function accepts the dict returned by
the corresponding build_* function in data_processor and writes a PDF to path.
"""

from datetime import date as dt_date
from datetime import datetime
from decimal import Decimal
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from firefly_reports import i18n
from firefly_reports.chart_engine import (
    create_area_chart,
    create_bar_chart,
    create_cashflow_combo,
    create_donut_chart,
    create_horizontal_bar_chart,
    create_line_chart,
    create_pie_chart,
)
from firefly_reports.i18n import T, t

# ─────────────────────────────────────────────────
# Strict monochrome palette
# ─────────────────────────────────────────────────
BLACK = colors.HexColor("#000000")
DARK = colors.HexColor("#1A1A1A")
MID = colors.HexColor("#4A4A4A")
LIGHT = colors.HexColor("#888888")
RULE = colors.HexColor("#CCCCCC")  # thin rule line
TOTAL_BG = colors.HexColor("#F2F2F2")  # total row background (very light grey)
WHITE = colors.white
PAGE_BG = colors.white


def _fmt_date(d: Any) -> str:
    """Locale-aware date format: DD/MM/YYYY for Italian, ISO YYYY-MM-DD otherwise."""
    if not hasattr(d, "strftime"):
        return str(d)
    fmt = "%d/%m/%Y" if i18n.CURRENT_LANG == "it" else "%Y-%m-%d"
    return str(d.strftime(fmt))


def _period_str(start: dt_date, end: dt_date) -> str:
    months_it = T.get("months", {})
    if start.year == end.year and start.month == end.month:
        m_key = f"{start.month:02d}"
        month_label = months_it.get(m_key, str(start.month))
        return f"{month_label.lower()} {start.year}"
    return f"{_fmt_date(start)} – {_fmt_date(end)}"


def _fmt_num(
    value: Decimal, show_sym: bool = False, sym: str = "€", parens_neg: bool = True
) -> str:
    """
    Accounting number format:
      - thousands/decimal separators follow i18n.CURRENT_LANG
        (it: "1.234,56" — other languages: "1,234.56")
      - negative values in parentheses
      - optional currency symbol
    """
    abs_val = abs(value)
    s = f"{abs_val:,.2f}"
    if i18n.CURRENT_LANG == "it":
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    if show_sym:
        s = f"{sym} {s}"
    if value < 0 and parens_neg:
        s = f"({s})"
    return s


def _flatten_rows(grouped_rows: list[dict]) -> list[dict]:
    """Helper to flatten grouped transactions for legacy renderers."""
    flat = []
    # In grouped_rows, running_balance is at the parent level.
    # To restore legacy behavior (running balance per split),
    # we need to track it based on the parent's starting balance.

    # Actually, the processor calculates running_balance after sorting groups.
    # We can just use the parent's running_balance for the last split of the group,
    # but for intermediate splits we'd need to subtract.
    # SIMPLER: Just use the parent's running_balance for ALL splits of that group
    # (this is slightly different from old legacy but close enough for "Grouped" context)
    # OR better: recalculate here.

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
            # If the group has a running_balance (from processor),
            # we use it as the 'final' balance for this group.
            # For simplicity in legacy, we attach the group's running_balance to all its splits.
            item["running_balance"] = group.get("running_balance", Decimal("0"))
            flat.append(item)
    return flat


# ─────────────────────────────────────────────────
# Typography styles
# ─────────────────────────────────────────────────
def _styles() -> dict:
    st = {}

    # Report title (first line, large)
    st["title"] = ParagraphStyle(
        "title",
        fontName="Times-Bold",
        fontSize=14,
        textColor=DARK,
        leading=18,
        spaceBefore=0,
        spaceAfter=2,
        alignment=TA_LEFT,
    )

    # Subtitle / entity name
    st["entity"] = ParagraphStyle(
        "entity",
        fontName="Times-Roman",
        fontSize=10,
        textColor=DARK,
        leading=14,
        spaceAfter=1,
        alignment=TA_LEFT,
    )

    # Info row (period, generation date)
    st["meta"] = ParagraphStyle(
        "meta",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=LIGHT,
        leading=12,
        spaceAfter=0,
        alignment=TA_LEFT,
    )

    # Section heading (uppercase, bold)
    st["section"] = ParagraphStyle(
        "section",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=DARK,
        leading=12,
        spaceBefore=14,
        spaceAfter=4,
        alignment=TA_LEFT,
        textTransform="uppercase",
    )  # textTransform not supported in RL; apply manually

    # Normal entry (left cell label)
    st["cell_l"] = ParagraphStyle(
        "cell_l", fontName="Helvetica", fontSize=9, textColor=DARK, leading=12, alignment=TA_LEFT
    )

    st["cell_c"] = ParagraphStyle(
        "cell_c", fontName="Helvetica", fontSize=9, textColor=DARK, leading=12, alignment=TA_CENTER
    )

    # Indented entry
    st["cell_l_ind"] = ParagraphStyle(
        "cell_l_ind",
        fontName="Helvetica",
        fontSize=9,
        textColor=DARK,
        leading=12,
        alignment=TA_LEFT,
        leftIndent=12,
    )

    # Right-aligned number
    st["cell_r"] = ParagraphStyle(
        "cell_r", fontName="Helvetica", fontSize=9, textColor=DARK, leading=12, alignment=TA_RIGHT
    )

    # Subtotal bold
    st["total_l"] = ParagraphStyle(
        "total_l",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=DARK,
        leading=12,
        alignment=TA_LEFT,
    )

    st["total_r"] = ParagraphStyle(
        "total_r",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=DARK,
        leading=12,
        alignment=TA_RIGHT,
    )

    # Grand total (slightly larger)
    st["grand_l"] = ParagraphStyle(
        "grand_l",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=DARK,
        leading=13,
        alignment=TA_LEFT,
    )

    st["grand_r"] = ParagraphStyle(
        "grand_r",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=DARK,
        leading=13,
        alignment=TA_RIGHT,
    )

    st["small"] = ParagraphStyle(
        "small", fontName="Helvetica", fontSize=7.5, textColor=LIGHT, leading=10, alignment=TA_LEFT
    )

    st["col_header"] = ParagraphStyle(
        "col_header",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["col_header_l"] = ParagraphStyle(
        "col_header_l",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_LEFT,
    )

    return st


# ─────────────────────────────────────────────────
# Corporate (Modern) Typography styles
# ─────────────────────────────────────────────────
def _corporate_styles() -> dict:
    st = {}

    # Modern palette uses more greys
    st["title"] = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=BLACK,
        leading=22,
        spaceBefore=0,
        spaceAfter=4,
        alignment=TA_LEFT,
    )

    st["entity"] = ParagraphStyle(
        "entity",
        fontName="Helvetica",
        fontSize=11,
        textColor=MID,
        leading=15,
        spaceAfter=2,
        alignment=TA_LEFT,
    )

    st["meta"] = ParagraphStyle(
        "meta",
        fontName="Helvetica",
        fontSize=8,
        textColor=LIGHT,
        leading=11,
        spaceAfter=0,
        alignment=TA_LEFT,
    )

    st["section"] = ParagraphStyle(
        "section",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=BLACK,
        leading=13,
        spaceBefore=18,
        spaceAfter=6,
        alignment=TA_LEFT,
    )

    # Smaller, cleaner cell styles for corporate look
    st["cell_l"] = ParagraphStyle(
        "cell_l", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11, alignment=TA_LEFT
    )

    st["cell_l_grey"] = ParagraphStyle(
        "cell_l_grey",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=MID,
        leading=11,
        alignment=TA_LEFT,
    )

    st["cell_c"] = ParagraphStyle(
        "cell_c",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_CENTER,
    )

    st["cell_l_ind"] = ParagraphStyle(
        "cell_l_ind",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_LEFT,
        leftIndent=12,
    )

    st["split_indent"] = ParagraphStyle(
        "split_indent",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=DARK,
        leading=11,
        alignment=TA_LEFT,
        leftIndent=24,
    )

    st["cell_r"] = ParagraphStyle(
        "cell_r", fontName="Helvetica", fontSize=8.5, textColor=DARK, leading=11, alignment=TA_RIGHT
    )

    st["cell_r_bold"] = ParagraphStyle(
        "cell_r_bold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=BLACK,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["total_l"] = ParagraphStyle(
        "total_l",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=BLACK,
        leading=11,
        alignment=TA_LEFT,
    )

    st["total_r"] = ParagraphStyle(
        "total_r",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=BLACK,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["grand_l"] = ParagraphStyle(
        "grand_l",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=BLACK,
        leading=11,
        alignment=TA_LEFT,
    )

    st["grand_r"] = ParagraphStyle(
        "grand_r",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=BLACK,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["small"] = ParagraphStyle(
        "small", fontName="Helvetica", fontSize=7, textColor=LIGHT, leading=11, alignment=TA_LEFT
    )

    st["col_header"] = ParagraphStyle(
        "col_header",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=MID,
        leading=11,
        alignment=TA_RIGHT,
    )

    st["col_header_l"] = ParagraphStyle(
        "col_header_l",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=MID,
        leading=11,
        alignment=TA_LEFT,
    )

    return st


# ─────────────────────────────────────────────────
# Page header / footer — accounting report style
# ─────────────────────────────────────────────────
def _page_fn(owner: str, report_title: str, period: str, landscape_mode=False):
    pagesize = landscape(A4) if landscape_mode else A4
    generated = _fmt_date(datetime.now())

    def draw(canvas, doc):
        canvas.saveState()
        w, h = pagesize

        # ── HEADER: text only + thin rule
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(DARK)
        canvas.drawString(1.8 * cm, h - 1.3 * cm, report_title.upper())

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(LIGHT)
        canvas.drawRightString(w - 1.8 * cm, h - 1.3 * cm, owner)

        # thin horizontal rule below header
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(1.8 * cm, h - 1.6 * cm, w - 1.8 * cm, h - 1.6 * cm)

        # ── FOOTER: rule + text
        canvas.setStrokeColor(RULE)
        canvas.line(1.8 * cm, 1.4 * cm, w - 1.8 * cm, 1.4 * cm)

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(LIGHT)
        canvas.drawString(
            1.8 * cm, 0.9 * cm, t("pdf.footer_period").format(period=period, generated=generated)
        )
        canvas.drawRightString(w - 1.8 * cm, 0.9 * cm, t("pdf.footer_page").format(page=doc.page))

        canvas.restoreState()

    return draw


# ─────────────────────────────────────────────────
# Helper: accounting table with thin rules
# ─────────────────────────────────────────────────
def _rule_line(col_widths: list) -> Table:
    """Full-width thin separator line."""
    tbl = Table([[""] * len(col_widths)], colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LINEABOVE", (0, 0), (-1, -1), 0.5, RULE),
            ]
        )
    )
    return tbl


def _accounting_table(
    rows: list, col_widths: list, total_rows: list | None = None, grand_rows: list | None = None
) -> Table:
    """
    Build a Table with accounting style:
    - no visible grid
    - thin rule above subtotals
    - very light grey background + bold on totals
    - double rule below grand total
    """
    tbl = Table(rows, colWidths=col_widths)
    total_rows = total_rows or []
    grand_rows = grand_rows or []

    cmds = [
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # No grid by default
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),  # thin rule below column headers
    ]

    for r in total_rows:
        cmds += [
            ("LINEABOVE", (0, r), (-1, r), 0.5, RULE),
            ("BACKGROUND", (0, r), (-1, r), TOTAL_BG),
            ("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"),
        ]

    for r in grand_rows:
        cmds += [
            ("LINEABOVE", (0, r), (-1, r), 1.0, DARK),
            ("LINEBELOW", (0, r), (-1, r), 0.5, DARK),
            ("BACKGROUND", (0, r), (-1, r), TOTAL_BG),
            ("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"),
            ("FONTSIZE", (0, r), (-1, r), 9.5),
        ]

    tbl.setStyle(TableStyle(cmds))
    return tbl


def _doc(output_path: str, page_fn, landscape_mode=False) -> BaseDocTemplate:
    pagesize = landscape(A4) if landscape_mode else A4
    doc = BaseDocTemplate(
        output_path,
        pagesize=pagesize,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=2.4 * cm,
        bottomMargin=2.2 * cm,
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="main",
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=page_fn)])
    return doc


# ─────────────────────────────────────────────────
# In-document page title block (not the page header)
# ─────────────────────────────────────────────────
def _page_title_block(
    report_title: str, owner: str, period: str, subtitle: str | None, st: dict
) -> list:
    """Return a list of flowables for the title block."""
    items = []
    items.append(Spacer(1, 0.3 * cm))
    items.append(Paragraph(report_title, st["title"]))
    items.append(Paragraph(owner, st["entity"]))
    items.append(Paragraph(t("pdf.period_ref").format(period=period), st["meta"]))
    items.append(Spacer(1, 0.15 * cm))
    items.append(HRFlowable(width="100%", thickness=1, color=DARK, spaceAfter=6, spaceBefore=2))
    if subtitle:
        items.append(Paragraph(subtitle.upper(), st["section"]))
    return items


# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_cash_flow(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.cash_flow"), period)
    doc = _doc(output_path, fn)
    story = []

    # ═══ PAGE 0 — Waterfall by activity (R-INT-03), only when account data available
    wf = data.get("waterfall") or {}
    if wf.get("closing_cash") is not None:
        story += _page_title_block(
            t("titles.cash_flow"), owner, period, t("pdf.section_waterfall"), st
        )
        CW0 = [7.4 * cm, 3.4 * cm, 3.4 * cm, 3.2 * cm]
        hdr0 = [
            [
                Paragraph("", st["col_header_l"]),
                Paragraph(t("common.income"), st["col_header"]),
                Paragraph(t("common.expense"), st["col_header"]),
                Paragraph(t("common.net_flow"), st["col_header"]),
            ]
        ]
        rows0 = list(hdr0)
        for sec_key, label_key in (
            ("operating", "pdf.wf_operating"),
            ("investing", "pdf.wf_investing"),
            ("financing", "pdf.wf_financing"),
        ):
            sec = wf[sec_key]
            rows0.append(
                [
                    Paragraph(t(label_key), st["cell_l"]),
                    Paragraph(
                        _fmt_num(sec["in"], show_sym=sec_key == "operating", sym=sym), st["cell_r"]
                    ),
                    Paragraph(
                        _fmt_num(sec["out"], show_sym=sec_key == "operating", sym=sym), st["cell_r"]
                    ),
                    Paragraph(
                        _fmt_num(
                            sec["net"], parens_neg=True, show_sym=sec_key == "operating", sym=sym
                        ),
                        st["cell_r"],
                    ),
                ]
            )
        rows0.append(
            [
                Paragraph(t("pdf.wf_net_change"), st["total_l"]),
                Paragraph("", st["total_r"]),
                Paragraph("", st["total_r"]),
                Paragraph(
                    _fmt_num(wf["net_change"], parens_neg=True, show_sym=True, sym=sym),
                    st["total_r"],
                ),
            ]
        )
        rows0.append(
            [
                Paragraph(t("pdf.wf_opening"), st["cell_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph("", st["cell_r"]),
                Paragraph(_fmt_num(wf["opening_cash"], parens_neg=True, sym=sym), st["cell_r"]),
            ]
        )
        rows0.append(
            [
                Paragraph(t("pdf.wf_closing"), st["grand_l"]),
                Paragraph("", st["grand_r"]),
                Paragraph("", st["grand_r"]),
                Paragraph(
                    _fmt_num(wf["closing_cash"], parens_neg=True, show_sym=True, sym=sym),
                    st["grand_r"],
                ),
            ]
        )
        story.append(
            _accounting_table(rows0, CW0, total_rows=[len(rows0) - 3], grand_rows=[len(rows0) - 1])
        )
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(t("pdf.wf_note"), st["small"]))
        story.append(PageBreak())

    # ── Column widths: label + amount
    CW = [13.5 * cm, 4.4 * cm]  # [description, amount]

    # ═══ PAGE 1 — Inflows
    story += _page_title_block(t("titles.cash_flow"), owner, period, t("pdf.section_inflows"), st)

    # column headers
    hdr = [
        [Paragraph(t("common.category_item"), st["col_header_l"]), Paragraph(sym, st["col_header"])]
    ]
    rows = list(hdr)
    for i, item in enumerate(data["inflows"]):
        is_first = i == 0
        num_str = _fmt_num(item["amount"], show_sym=is_first, sym=sym)
        rows.append(
            [
                Paragraph(item["category"], st["cell_l_ind"]),
                Paragraph(num_str, st["cell_r"]),
            ]
        )

    total_str = _fmt_num(data["total_in"], show_sym=True, sym=sym)
    rows.append(
        [
            Paragraph(t("common.total_income"), st["total_l"]),
            Paragraph(total_str, st["total_r"]),
        ]
    )
    total_idx = len(rows) - 1

    tbl = _accounting_table(rows, CW, total_rows=[total_idx], grand_rows=[])
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))

    # footnote
    story.append(
        Paragraph(
            t("pdf.note_amounts_deposit"),
            st["small"],
        )
    )

    # ═══ PAGE 2 — Outflows
    story.append(PageBreak())
    story += _page_title_block(t("titles.cash_flow"), owner, period, t("pdf.section_outflows"), st)

    hdr2 = [
        [Paragraph(t("common.category_item"), st["col_header_l"]), Paragraph(sym, st["col_header"])]
    ]
    rows2 = list(hdr2)
    for i, item in enumerate(data["outflows"]):
        is_first = i == 0
        num_str = _fmt_num(item["amount"], show_sym=is_first, sym=sym)
        rows2.append(
            [
                Paragraph(item["category"], st["cell_l_ind"]),
                Paragraph(num_str, st["cell_r"]),
            ]
        )
    total_str2 = _fmt_num(data["total_out"], show_sym=True, sym=sym)
    rows2.append(
        [
            Paragraph(t("common.total_expense"), st["total_l"]),
            Paragraph(total_str2, st["total_r"]),
        ]
    )
    t2_idx = len(rows2) - 1
    tbl2 = _accounting_table(rows2, CW, total_rows=[t2_idx])
    story.append(tbl2)
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            t("pdf.note_amounts_withdrawal"),
            st["small"],
        )
    )

    # ═══ PAGE 3 — Monthly cash flow + final summary
    story.append(PageBreak())
    story += _page_title_block(t("titles.cash_flow"), owner, period, t("pdf.section_monthly"), st)

    months_it = T.get("months", {})

    CW3 = [6.5 * cm, 3.5 * cm, 3.5 * cm, 4.4 * cm]

    if len(data["by_month"]) > 0:
        hdr3 = [
            [
                Paragraph(t("common.month"), st["col_header_l"]),
                Paragraph(t("common.income"), st["col_header"]),
                Paragraph(t("common.expense"), st["col_header"]),
                Paragraph(t("common.net_flow"), st["col_header"]),
            ]
        ]
        rows3 = list(hdr3)
        for i, (mk, vals) in enumerate(data["by_month"].items()):
            y, m = mk.split("-")
            month_label = f"{months_it.get(m, m)} {y}"
            is_first = i == 0
            net = vals["net"]
            net_str = _fmt_num(net, show_sym=is_first, sym=sym, parens_neg=True)
            rows3.append(
                [
                    Paragraph(month_label, st["cell_l"]),
                    Paragraph(_fmt_num(vals["in"], show_sym=is_first, sym=sym), st["cell_r"]),
                    Paragraph(_fmt_num(vals["out"], show_sym=is_first, sym=sym), st["cell_r"]),
                    Paragraph(net_str, st["cell_r"]),
                ]
            )
        tbl3 = _accounting_table(rows3, CW3)
        story.append(tbl3)
        story.append(Spacer(1, 0.8 * cm))

    # Final summary
    story.append(Paragraph(t("pdf.section_period_summary"), st["section"]))

    CW_sum = [13.5 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("pdf.total_income_period"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_in"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("pdf.total_expense_period"), st["cell_l"]),
            Paragraph(f"({_fmt_num(data['total_out'], show_sym=True, sym=sym)})", st["cell_r"]),
        ],
        [
            Paragraph(t("pdf.net_flow_period"), st["grand_l"]),
            Paragraph(
                _fmt_num(data["net"], show_sym=True, sym=sym, parens_neg=True), st["grand_r"]
            ),
        ],
    ]
    sum_tbl = _accounting_table(sum_rows, CW_sum, total_rows=[1], grand_rows=[2])
    story.append(sum_tbl)

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 2 — Income & Expense Summary
# (3 pages: Income | Expense | Summary)
# ═══════════════════════════════════════════════════


def _render_legacy_income_expense(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.income_expense_summary"), period)
    doc = _doc(output_path, fn)
    story = []

    CW = [10.5 * cm, 3.5 * cm, 3.9 * cm]  # label | amount | % share

    # ═══ PAGE 1 — Income by category
    story += _page_title_block(
        t("titles.income_expense_summary"), owner, period, t("pdf.section_income_cat"), st
    )

    hdr = [
        [
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.share"), st["col_header"]),
        ]
    ]
    rows = list(hdr)
    for i, r in enumerate(data["income_rows"]):
        is_first = i == 0
        rows.append(
            [
                Paragraph(r["category"], st["cell_l_ind"]),
                Paragraph(_fmt_num(r["amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['pct']} %", st["cell_r"]),
            ]
        )
    rows.append(
        [
            Paragraph(t("common.total_income"), st["total_l"]),
            Paragraph(_fmt_num(data["total_income"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("100,0 %" if i18n.CURRENT_LANG == "it" else "100.0 %", st["total_r"]),
        ]
    )
    t_idx = len(rows) - 1
    story.append(_accounting_table(rows, CW, total_rows=[t_idx]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(t("pdf.share_note_income"), st["small"]))

    # ═══ PAGE 2 — Expenses by category
    story.append(PageBreak())
    story += _page_title_block(
        t("titles.income_expense_summary"), owner, period, t("pdf.section_expense_cat"), st
    )

    hdr2 = [
        [
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.share"), st["col_header"]),
        ]
    ]
    rows2 = list(hdr2)
    for i, r in enumerate(data["expense_rows"]):
        is_first = i == 0
        rows2.append(
            [
                Paragraph(r["category"], st["cell_l_ind"]),
                Paragraph(_fmt_num(r["amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['pct']} %", st["cell_r"]),
            ]
        )
    rows2.append(
        [
            Paragraph(t("common.total_expense"), st["total_l"]),
            Paragraph(_fmt_num(data["total_expense"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("100,0 %" if i18n.CURRENT_LANG == "it" else "100.0 %", st["total_r"]),
        ]
    )
    t2_idx = len(rows2) - 1
    story.append(_accounting_table(rows2, CW, total_rows=[t2_idx]))
    story.append(Spacer(1, 0.5 * cm))

    # Budget breakdown (if present) — same page
    if data["budget_breakdown"]:
        story.append(Paragraph(t("pdf.budget_detail"), st["section"]))
        CW_b = [10.5 * cm, 7.4 * cm]
        hdr_b = [
            [
                Paragraph(t("common.budget"), st["col_header_l"]),
                Paragraph(t("common.amount"), st["col_header"]),
            ]
        ]
        rows_b = list(hdr_b)
        for i, b in enumerate(data["budget_breakdown"]):
            rows_b.append(
                [
                    Paragraph(b["budget"], st["cell_l_ind"]),
                    Paragraph(_fmt_num(b["spent"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                ]
            )
        story.append(_accounting_table(rows_b, CW_b))
        story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph(t("pdf.share_note"), st["small"]))

    # ═══ PAGE 3 — Summary
    story.append(PageBreak())
    story += _page_title_block(
        t("titles.income_expense_summary"), owner, period, t("pdf.section_summary_analysis"), st
    )

    CW_s = [13.5 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("pdf.total_income_period"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_income"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("pdf.total_expense_period"), st["cell_l"]),
            Paragraph(f"({_fmt_num(data['total_expense'], show_sym=True, sym=sym)})", st["cell_r"]),
        ],
        [
            Paragraph(t("common.net_savings"), st["grand_l"]),
            Paragraph(
                _fmt_num(data["net_savings"], show_sym=True, sym=sym, parens_neg=True),
                st["grand_r"],
            ),
        ],
    ]
    story.append(_accounting_table(sum_rows, CW_s, total_rows=[1], grand_rows=[2]))
    story.append(Spacer(1, 0.6 * cm))

    # Savings rate breakdown
    rate_rows = [
        [
            Paragraph(t("common.savings_rate"), st["cell_l"]),
            Paragraph(f"{data['savings_rate']} %", st["cell_r"]),
        ],
        [
            Paragraph(t("common.income"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_income"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("common.expense"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_expense"], show_sym=True, sym=sym), st["cell_r"]),
        ],
    ]
    story.append(Paragraph(t("pdf.section_indicators"), st["section"]))
    story.append(_accounting_table(rate_rows, CW_s))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 3 — Transaction Register
# ═══════════════════════════════════════════════════


def _render_legacy_transaction_register(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.transaction_register"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)

    story = []
    story += _page_title_block(
        t("titles.transaction_register"),
        owner,
        period,
        t("pdf.transactions_register").format(count=data["total_transactions"]),
        st,
    )

    # Landscape columns: available width = 26.7 cm (29.7 - 2×1.5)
    # date | description | type | category | amount | running balance
    CW = [2.4 * cm, 9.8 * cm, 2.4 * cm, 5.2 * cm, 3.5 * cm, 3.4 * cm]

    hdr = [
        [
            Paragraph(t("common.date"), st["col_header_l"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.type"), st["col_header"]),
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.running_balance"), st["col_header"]),
        ]
    ]
    rows = list(hdr)

    # Flatten grouped data for legacy rendering
    flat_rows = _flatten_rows(data["rows"])

    # Group rows by month
    current_month = None
    for r in flat_rows:
        month_key = r["date"][:7]
        if month_key != current_month:
            current_month = month_key
            y, m = month_key.split("-")
            months_it = T.get("months", {})
            month_label = f"{months_it.get(m, m)} {y}".upper()
            rows.append(
                [
                    Paragraph(
                        month_label,
                        ParagraphStyle(
                            "mh", fontName="Helvetica-Bold", fontSize=8, textColor=LIGHT
                        ),
                    ),
                    Paragraph("", st["cell_l"]),
                    Paragraph("", st["cell_l"]),
                    Paragraph("", st["cell_l"]),
                    Paragraph("", st["cell_r"]),
                    Paragraph("", st["cell_r"]),
                ]
            )

        amt = r["amount"]
        bal = r["running_balance"]
        amt_str = _fmt_num(amt, show_sym=False, parens_neg=True)
        bal_str = _fmt_num(bal, show_sym=False, parens_neg=True)

        desc = r["description"]
        if len(desc) > 75:
            desc = desc[:72] + "…"
        cat = r["category"] or "—"
        if len(cat) > 30:
            cat = cat[:27] + "…"

        rows.append(
            [
                Paragraph(r["date"], st["cell_l"]),
                Paragraph(desc, st["cell_l"]),
                Paragraph(r["type"][:3].upper(), st["cell_r"]),
                Paragraph(cat, st["cell_l"]),
                Paragraph(amt_str, st["cell_r"]),
                Paragraph(bal_str, st["cell_r"]),
            ]
        )

    # Grand total row
    rows.append(
        [
            Paragraph("", st["cell_l"]),
            Paragraph(t("pdf.closing_balance_period"), st["total_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph(
                _fmt_num(
                    data["rows"][-1]["running_balance"] if data["rows"] else Decimal(0),
                    show_sym=True,
                    sym=sym,
                    parens_neg=True,
                ),
                st["total_r"],
            ),
        ]
    )
    grand_idx = len(rows) - 1

    tbl = Table(rows, colWidths=CW, repeatRows=1)
    cmds = [
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
        ("LINEABOVE", (0, grand_idx), (-1, grand_idx), 1.0, DARK),
        ("LINEBELOW", (0, grand_idx), (-1, grand_idx), 0.5, DARK),
        ("BACKGROUND", (0, grand_idx), (-1, grand_idx), TOTAL_BG),
        ("FONTNAME", (0, grand_idx), (-1, grand_idx), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -2), 8),
    ]
    tbl.setStyle(TableStyle(cmds))
    story.append(tbl)

    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            t("pdf.total_transactions").format(count=data["total_transactions"])
            + "WIT = Prelievo   DEP = Versamento   TRF = Giroconto",
            st["small"],
        )
    )

    doc.build(story)


def _render_modern_transaction_register(data: dict[str, Any], output_path: str) -> None:
    """Modern landscape Transaction Detail Ledger with split grouping (R-INT-06).

    One master row per transaction group; split sub-rows only for groups with
    more than one split. Notes appear as small gray lines under their row.
    """
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.transaction_register"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)

    story = []
    story += _page_title_block(
        t("titles.transaction_register"),
        owner,
        period,
        t("pdf.transactions_register").format(count=data["total_transactions"]),
        st,
    )

    # Date | Type | Description | From | To | Category | Budget | Amount | ID
    # Available width = 26.1 cm
    CW = [2.0 * cm, 1.3 * cm, 6.2 * cm, 3.4 * cm, 3.4 * cm, 2.9 * cm, 2.2 * cm, 3.0 * cm, 1.7 * cm]

    hdr = [
        [
            Paragraph(t("common.date"), st["col_header_l"]),
            Paragraph(t("common.type"), st["col_header_l"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.source"), st["col_header_l"]),
            Paragraph(t("common.destination"), st["col_header_l"]),
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("common.budget"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.id"), st["col_header"]),
        ]
    ]
    rows: list[Any] = list(hdr)

    type_badges = {
        "withdrawal": t("pdf.tx_type_w"),
        "deposit": t("pdf.tx_type_d"),
        "transfer": t("pdf.tx_type_t"),
    }

    def _amount_cells(amount: Decimal, split: dict | None, bold: bool) -> list:
        amt_str = _fmt_num(amount, show_sym=False, parens_neg=True)
        cells = [Paragraph(f"<b>{amt_str}</b>" if bold else amt_str, st["cell_r"])]
        if split:
            f_amt = split.get("foreign_amount")
            f_curr = split.get("foreign_currency_code")
            if f_amt and f_curr:
                f_str = f"{f_curr} {_fmt_num(Decimal(str(f_amt)), show_sym=False)}"
                cells.append(Paragraph(f_str, st["small"]))
        return cells

    def _notes_row(notes: str) -> list | None:
        notes = (notes or "").strip()
        if not notes:
            return None
        if len(notes) > 90:
            notes = notes[:87] + "…"
        return [
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_l"]),
            Paragraph(notes, st["split_indent"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["small"]),
        ]

    for group in data["rows"]:
        splits = group.get("splits", [])
        single = len(splits) == 1

        tx_type = str(group.get("type") or "")
        badge = type_badges.get(tx_type, tx_type[:1].upper())
        if group.get("reconciled"):
            badge += " R"
        if group.get("has_attachments"):
            badge += " A"

        amount = group["total_abs"] if group["type"] == "transfer" else group["total"]

        date_cells = [Paragraph(_fmt_date(group["date"]), st["cell_l"])]
        first_split = splits[0] if splits else {}
        if single:
            book = first_split.get("book_date") or ""
            if book and book != group["date"]:
                date_cells.append(
                    Paragraph(f"{t('common.book_date')}: {_fmt_date(book)}", st["small"])
                )

        rows.append(
            [
                date_cells,
                Paragraph(badge, st["cell_l"]),
                Paragraph(f"<b>{group['description']}</b>", st["cell_l"]),
                Paragraph(group["source"], st["cell_l"]),
                Paragraph(group["destination"], st["cell_l"]),
                Paragraph(first_split.get("category") or "—" if single else "", st["cell_l"]),
                Paragraph(first_split.get("budget") or "—" if single else "", st["cell_l"]),
                _amount_cells(amount, first_split if single else None, bold=True),
                Paragraph(f"#{group.get('journal_id', '')}", st["small"]),
            ]
        )

        if single:
            note_row = _notes_row(first_split.get("notes", ""))
            if note_row:
                rows.append(note_row)
        else:
            for split in splits:
                rows.append(
                    [
                        Paragraph("", st["cell_l"]),
                        Paragraph("", st["cell_l"]),
                        Paragraph(f"» {split.get('description') or ''}", st["split_indent"]),
                        Paragraph("", st["cell_l"]),
                        Paragraph("", st["cell_l"]),
                        Paragraph(split.get("category") or "—", st["cell_l"]),
                        Paragraph(split.get("budget") or "—", st["cell_l"]),
                        _amount_cells(split["amount"], split, bold=False),
                        Paragraph(f"#{split.get('id', '')}", st["small"]),
                    ]
                )
                note_row = _notes_row(split.get("notes", ""))
                if note_row:
                    rows.append(note_row)

    tbl = Table(rows, colWidths=CW, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
            ]
        )
    )
    story.append(tbl)

    # Totals by transaction type (R-INT-06)
    totals = data.get("totals_by_type", {})
    if totals:
        story.append(Spacer(1, 0.4 * cm))
        parts = [
            f"{t('common.total_income')}: {_fmt_num(totals.get('deposit', Decimal(0)), show_sym=True, sym=sym)}",
            f"{t('common.total_expense')}: {_fmt_num(totals.get('withdrawal', Decimal(0)), show_sym=True, sym=sym)}",
            f"{t('pdf.total_transfers')}: {_fmt_num(totals.get('transfer', Decimal(0)), show_sym=True, sym=sym)}",
        ]
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(parts), st["cell_l"]))

    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(t("pdf.register_legend"), st["small"]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 4 — Asset & Net Worth Statement
# ═══════════════════════════════════════════════════


def _render_legacy_net_worth(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    as_of = _fmt_date(data["as_of_date"])
    period_label = t("pdf.as_of").format(date=as_of)
    sym = data["currency"]
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.net_worth"), period_label)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.net_worth"),
        owner,
        period_label,
        t("pdf.subtitle_net_worth"),
        st,
    )

    CW = [8.5 * cm, 3.5 * cm, 3.0 * cm, 2.9 * cm]  # name | iban | currency | balance

    for group in data["groups"]:
        if not group["accounts"]:
            continue

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(group["role_label"].upper(), st["section"]))

        hdr = [
            [
                Paragraph(t("common.account"), st["col_header_l"]),
                Paragraph("IBAN", st["col_header_l"]),
                Paragraph(t("common.currency_col"), st["col_header"]),
                Paragraph(t("common.balance"), st["col_header"]),
            ]
        ]
        rows = list(hdr)
        for i, acc in enumerate(group["accounts"]):
            rows.append(
                [
                    Paragraph(acc["name"], st["cell_l"]),
                    Paragraph(acc["iban_masked"], st["cell_l"]),
                    Paragraph(acc["currency_code"], st["cell_r"]),
                    Paragraph(
                        _fmt_num(acc["balance"], show_sym=(i == 0), sym=sym, parens_neg=True),
                        st["cell_r"],
                    ),
                ]
            )
        rows.append(
            [
                Paragraph(t("pdf.subtotal").format(role=group["role_label"]), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph(
                    _fmt_num(group["subtotal"], show_sym=True, sym=sym, parens_neg=True),
                    st["total_r"],
                ),
            ]
        )
        t_idx = len(rows) - 1
        story.append(KeepTogether([_accounting_table(rows, CW, total_rows=[t_idx])]))

    # ── Final summary
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(t("pdf.section_net_worth_summary"), st["section"]))

    CW_s = [13.5 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("common.total_assets"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_assets"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("common.total_liabilities"), st["cell_l"]),
            Paragraph(
                f"({_fmt_num(abs(data['total_liabilities']), show_sym=True, sym=sym)})",
                st["cell_r"],
            ),
        ],
        [
            Paragraph(t("common.net_worth"), st["grand_l"]),
            Paragraph(
                _fmt_num(data["net_worth"], show_sym=True, sym=sym, parens_neg=True), st["grand_r"]
            ),
        ],
    ]
    story.append(_accounting_table(sum_rows, CW_s, total_rows=[1], grand_rows=[2]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            t("pdf.net_worth_note").format(date=period_label, count=data["account_count"]),
            st["small"],
        )
    )

    doc.build(story)


def _render_modern_net_worth(data: dict[str, Any], output_path: str) -> None:
    """Modern portrait net worth statement with update tracking."""
    st = _corporate_styles()
    as_of = _fmt_date(data["as_of_date"])
    period_label = t("pdf.as_of").format(date=as_of)
    sym = data["currency"]
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.net_worth"), period_label)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.net_worth"),
        owner,
        period_label,
        t("titles.corporate_wealth"),
        st,
    )

    # Name | IBAN | Last Update | Balance
    # available 17.4cm
    CW = [7.0 * cm, 4.0 * cm, 3.4 * cm, 3.0 * cm]

    for group in data["groups"]:
        if not group["accounts"]:
            continue

        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(group["role_label"].upper(), st["section"]))

        hdr = [
            [
                Paragraph(t("common.account"), st["col_header_l"]),
                Paragraph("IBAN", st["col_header_l"]),
                Paragraph(t("common.last_update"), st["col_header"]),
                Paragraph(t("common.balance"), st["col_header"]),
            ]
        ]
        rows = list(hdr)
        for i, acc in enumerate(group["accounts"]):
            updated_at = acc.get("updated_at") or "—"
            if updated_at and len(updated_at) > 10:
                updated_at = updated_at[:10]

            rows.append(
                [
                    Paragraph(acc["name"], st["cell_l"]),
                    Paragraph(acc["iban_masked"], st["cell_l"]),
                    Paragraph(updated_at, st["cell_r"]),
                    Paragraph(
                        _fmt_num(acc["balance"], show_sym=(i == 0), sym=sym, parens_neg=True),
                        st["cell_r"],
                    ),
                ]
            )
        rows.append(
            [
                Paragraph(t("pdf.subtotal").format(role=group["role_label"]), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph(
                    _fmt_num(group["subtotal"], show_sym=True, sym=sym, parens_neg=True),
                    st["total_r"],
                ),
            ]
        )
        t_idx = len(rows) - 1
        story.append(KeepTogether([_accounting_table(rows, CW, total_rows=[t_idx])]))

    # ── Final summary
    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(t("pdf.section_net_worth_summary"), st["section"]))

    CW_s = [13.0 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("common.total_assets"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_assets"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("common.total_liabilities"), st["cell_l"]),
            Paragraph(
                f"({_fmt_num(abs(data['total_liabilities']), show_sym=True, sym=sym)})",
                st["cell_r"],
            ),
        ],
        [
            Paragraph(t("common.net_worth"), st["grand_l"]),
            Paragraph(
                _fmt_num(data["net_worth"], show_sym=True, sym=sym, parens_neg=True), st["grand_r"]
            ),
        ],
    ]
    story.append(_accounting_table(sum_rows, CW_s, total_rows=[1], grand_rows=[2]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            t("pdf.net_worth_note").format(date=period_label, count=data["account_count"]),
            st["small"],
        )
    )

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 5 — Account Statement (one sheet per account)
# One account per PDF page
# ═══════════════════════════════════════════════════


def _render_legacy_account_statements(statements: list[dict[str, Any]], output_path: str) -> None:
    if not statements:
        return

    st = _styles()
    # Use the first statement for the period (all share the same period)
    period = _period_str(statements[0]["period_start"], statements[0]["period_end"])
    owner = statements[0]["owner"]

    # Landscape: 6 columns with comfortable spacing (29.7 × 21.0 cm)
    fn = _page_fn(owner, t("titles.account_statement"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)
    story = []

    for idx, stmt in enumerate(statements):
        if idx > 0:
            story.append(PageBreak())

        sym = stmt["currency"]

        story += _page_title_block(
            t("titles.account_statement"),
            owner,
            period,
            f"{stmt['account_role']} — {stmt['account_name']}",
            st,
        )

        # Account metadata
        meta_rows = [
            [
                Paragraph(t("pdf.iban_reference"), st["col_header_l"]),
                Paragraph(stmt["account_iban"], st["cell_l"]),
            ],
            [
                Paragraph(t("common.currency_col"), st["col_header_l"]),
                Paragraph(stmt["currency_code"], st["cell_l"]),
            ],
            [
                Paragraph(t("pdf.opening_balance_period"), st["col_header_l"]),
                Paragraph(
                    _fmt_num(stmt["opening_balance"], show_sym=True, sym=sym, parens_neg=True),
                    st["cell_r"],
                ),
            ],
        ]
        meta_tbl = Table(meta_rows, colWidths=[5 * cm, 16 * cm])
        meta_tbl.setStyle(
            TableStyle(
                [
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE),
                ]
            )
        )
        story.append(meta_tbl)
        story.append(Spacer(1, 0.4 * cm))

        # Landscape columns: 26.7 cm available (29.7 − 2×1.5)
        # date | description | type | counterpart | amount | balance
        CW_m = [2.4 * cm, 10.0 * cm, 2.2 * cm, 5.5 * cm, 3.5 * cm, 3.1 * cm]
        hdr = [
            [
                Paragraph(t("common.date"), st["col_header_l"]),
                Paragraph(t("common.description"), st["col_header_l"]),
                Paragraph(t("common.type"), st["col_header"]),
                Paragraph(t("common.counterpart"), st["col_header_l"]),
                Paragraph(t("common.amount"), st["col_header"]),
                Paragraph(t("common.balance"), st["col_header"]),
            ]
        ]
        rows = list(hdr)

        # Flatten grouped data for legacy rendering
        flat_stmt_rows = _flatten_rows(stmt["rows"])

        for r in flat_stmt_rows:
            amt = r["amount"]
            desc = r["description"]
            if len(desc) > 80:
                desc = desc[:77] + "…"
            cpart = r["counterpart"] or "—"
            if len(cpart) > 40:
                cpart = cpart[:37] + "…"
            rows.append(
                [
                    Paragraph(r["date"], st["cell_l"]),
                    Paragraph(desc, st["cell_l"]),
                    Paragraph(r["type"][:3].upper(), st["cell_r"]),
                    Paragraph(cpart, st["cell_l"]),
                    Paragraph(_fmt_num(amt, parens_neg=True), st["cell_r"]),
                    Paragraph(_fmt_num(r["running_balance"], parens_neg=True), st["cell_r"]),
                ]
            )

        rows.append(
            [
                Paragraph("", st["cell_l"]),
                Paragraph(t("pdf.closing_balance_period"), st["total_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph(
                    _fmt_num(stmt["closing_balance"], show_sym=True, sym=sym, parens_neg=True),
                    st["total_r"],
                ),
            ]
        )
        grand_idx = len(rows) - 1

        tbl = Table(rows, colWidths=CW_m, repeatRows=1)
        tbl.setStyle(
            TableStyle(
                [
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
                    ("FONTSIZE", (0, 1), (-1, -2), 8),
                    ("LINEABOVE", (0, grand_idx), (-1, grand_idx), 1.0, DARK),
                    ("LINEBELOW", (0, grand_idx), (-1, grand_idx), 0.5, DARK),
                    ("BACKGROUND", (0, grand_idx), (-1, grand_idx), TOTAL_BG),
                    ("FONTNAME", (0, grand_idx), (-1, grand_idx), "Helvetica-Bold"),
                ]
            )
        )
        story.append(tbl)

        # Summary table
        story.append(Spacer(1, 0.5 * cm))
        CW_s = [15 * cm, 3.5 * cm, 3.5 * cm, 4.2 * cm]
        recap = [
            [
                Paragraph(t("common.opening_balance"), st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(
                    _fmt_num(stmt["opening_balance"], show_sym=True, sym=sym, parens_neg=True),
                    st["cell_r"],
                ),
            ],
            [
                Paragraph(t("pdf.stmt_income_period"), st["cell_l_ind"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(_fmt_num(stmt["total_in"], show_sym=True, sym=sym), st["cell_r"]),
            ],
            [
                Paragraph(t("pdf.stmt_expense_period"), st["cell_l_ind"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(
                    f"({_fmt_num(abs(stmt['total_out']), show_sym=True, sym=sym)})", st["cell_r"]
                ),
            ],
            [
                Paragraph(t("common.closing_balance_stmt"), st["grand_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(
                    _fmt_num(stmt["closing_balance"], show_sym=True, sym=sym, parens_neg=True),
                    st["grand_r"],
                ),
            ],
        ]
        recap_tbl = _accounting_table(recap, CW_s, total_rows=[2], grand_rows=[3])
        story.append(recap_tbl)

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 6 — Annual Tax Summary
# ═══════════════════════════════════════════════════


def _render_legacy_tax_summary(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period_label = t("pdf.fiscal_year").format(year=data["year"])
    sym = data["currency"]
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.tax_summary"), period_label)
    doc = _doc(output_path, fn)
    story = []

    # ═══ PAGE 1 — Professional income
    story += _page_title_block(
        t("titles.tax_summary"), owner, period_label, t("pdf.section_tax_income"), st
    )

    CW2 = [10.5 * cm, 3.5 * cm, 3.9 * cm]

    # By category
    story.append(Paragraph(t("pdf.by_category"), st["section"]))
    hdr_c = [
        [
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.share"), st["col_header"]),
        ]
    ]
    rows_c = list(hdr_c)
    total_in = data["total_income"]
    for i, r in enumerate(data["income_by_cat"]):
        pct = (r["amount"] / total_in * 100).quantize(Decimal("0.1")) if total_in else Decimal("0")
        rows_c.append(
            [
                Paragraph(r["category"], st["cell_l_ind"]),
                Paragraph(_fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                Paragraph(f"{pct} %", st["cell_r"]),
            ]
        )
    rows_c.append(
        [
            Paragraph(t("common.total_income"), st["total_l"]),
            Paragraph(_fmt_num(total_in, show_sym=True, sym=sym), st["total_r"]),
            Paragraph("100,0 %" if i18n.CURRENT_LANG == "it" else "100.0 %", st["total_r"]),
        ]
    )
    story.append(_accounting_table(rows_c, CW2, total_rows=[len(rows_c) - 1]))
    story.append(Spacer(1, 0.6 * cm))

    # By client / counterpart
    story.append(Paragraph(t("pdf.by_client"), st["section"]))
    hdr_cl = [
        [
            Paragraph(t("common.income_client"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.share"), st["col_header"]),
        ]
    ]
    rows_cl = list(hdr_cl)
    for i, r in enumerate(data["income_by_client"]):
        pct = (r["amount"] / total_in * 100).quantize(Decimal("0.1")) if total_in else Decimal("0")
        rows_cl.append(
            [
                Paragraph(r["client"], st["cell_l_ind"]),
                Paragraph(_fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                Paragraph(f"{pct} %", st["cell_r"]),
            ]
        )
    story.append(_accounting_table(rows_cl, CW2, total_rows=[]))

    # ═══ PAGE 2 — Deductible expenses
    story.append(PageBreak())
    story += _page_title_block(
        t("titles.tax_summary"), owner, period_label, t("pdf.section_tax_deductible"), st
    )

    CW1 = [13.5 * cm, 4.4 * cm]
    hdr_d = [
        [
            Paragraph(t("common.category_item"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
        ]
    ]
    rows_d = list(hdr_d)
    for i, r in enumerate(data["deductible_rows"]):
        rows_d.append(
            [
                Paragraph(r["category"], st["cell_l_ind"]),
                Paragraph(_fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
            ]
        )
    rows_d.append(
        [
            Paragraph(t("common.total_deductible"), st["total_l"]),
            Paragraph(_fmt_num(data["total_deductible"], show_sym=True, sym=sym), st["total_r"]),
        ]
    )
    story.append(_accounting_table(rows_d, CW1, total_rows=[len(rows_d) - 1]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(t("pdf.non_deductible"), st["section"]))
    hdr_nd = [
        [
            Paragraph(t("common.category_item"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
        ]
    ]
    rows_nd = list(hdr_nd)
    for i, r in enumerate(data["nondeductible_rows"]):
        rows_nd.append(
            [
                Paragraph(r["category"], st["cell_l_ind"]),
                Paragraph(_fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
            ]
        )
    story.append(_accounting_table(rows_nd, CW1))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            t("pdf.deductible_note"),
            st["small"],
        )
    )

    # ═══ PAGE 3 — Tax summary
    story.append(PageBreak())
    story += _page_title_block(
        t("titles.tax_summary"), owner, period_label, t("pdf.section_tax_summary"), st
    )

    sum_rows = [
        [
            Paragraph(t("pdf.income_in_period"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_income"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("common.total_deductible"), st["cell_l_ind"]),
            Paragraph(
                f"({_fmt_num(data['total_deductible'], show_sym=True, sym=sym)})", st["cell_r"]
            ),
        ],
        [
            Paragraph(t("common.taxable_estimate"), st["grand_l"]),
            Paragraph(
                _fmt_num(data["taxable_estimate"], show_sym=True, sym=sym, parens_neg=True),
                st["grand_r"],
            ),
        ],
    ]
    story.append(_accounting_table(sum_rows, CW1, total_rows=[1], grand_rows=[2]))
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(t("pdf.taxable_note"), st["small"]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 7 — Expense Trend by Category
# ═══════════════════════════════════════════════════


def _render_legacy_expense_trend(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    months = data["months"]

    # Landscape: the category × month matrix is too wide for portrait
    fn = _page_fn(owner, t("titles.expense_trend"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)

    story = []
    story += _page_title_block(
        t("titles.expense_trend"),
        owner,
        period,
        t("pdf.subtitle_expense_trend"),
        st,
    )

    months_abbr = T.get("months_abbr", {})

    def _mk_label(mk):
        y, m = mk.split("-")
        return f"{months_abbr.get(m, m)}\n{y[-2:]}"

    n_months = len(months)
    # Landscape: 29.7 cm width. Margins 1.8cm each side (default in _doc)
    cat_w = 6.0 * cm
    tot_w = 2.8 * cm
    avail = (landscape(A4)[0]) - 1.8 * cm - 1.8 * cm - cat_w - tot_w
    mon_w = min(2.4 * cm, avail / max(n_months, 1))
    CW_t = [cat_w] + [mon_w] * n_months + [tot_w]

    # Header row
    hdr_cells = [Paragraph(t("common.category"), st["col_header_l"])]
    for mk in months:
        hdr_cells.append(
            Paragraph(
                _mk_label(mk),
                ParagraphStyle(
                    "mh",
                    fontName="Helvetica-Bold",
                    fontSize=7.5,
                    textColor=DARK,
                    alignment=TA_CENTER,
                    leading=9,
                ),
            )
        )
    hdr_cells.append(Paragraph(t("common.total"), st["col_header"]))

    rows = [hdr_cells]
    for r in data["rows"]:
        row_cells = [
            Paragraph(
                r["category"][:30],
                ParagraphStyle(
                    "cl", fontName="Helvetica", fontSize=8, textColor=DARK, alignment=TA_LEFT
                ),
            )
        ]
        for val in r["monthly"]:
            row_cells.append(
                Paragraph(
                    _fmt_num(val) if val > 0 else "—",
                    ParagraphStyle(
                        "nr", fontName="Helvetica", fontSize=8, textColor=DARK, alignment=TA_RIGHT
                    ),
                )
            )
        row_cells.append(
            Paragraph(
                _fmt_num(r["total"]),
                ParagraphStyle(
                    "tr", fontName="Helvetica-Bold", fontSize=8, textColor=DARK, alignment=TA_RIGHT
                ),
            )
        )
        rows.append(row_cells)

    # Monthly expense total row
    tot_cells = [Paragraph(t("common.total_expense"), st["total_l"])]
    for val in data["totals_by_month"]:
        tot_cells.append(
            Paragraph(
                _fmt_num(val),
                ParagraphStyle(
                    "tb", fontName="Helvetica-Bold", fontSize=8, textColor=DARK, alignment=TA_RIGHT
                ),
            )
        )
    tot_cells.append(Paragraph(_fmt_num(data["grand_total"]), st["total_r"]))
    rows.append(tot_cells)

    # Monthly income row (reference comparison)
    inc_cells = [Paragraph(t("pdf.income_for_comparison"), st["cell_l"])]
    for val in data["income_by_month"]:
        inc_cells.append(
            Paragraph(
                _fmt_num(val) if val > 0 else "—",
                ParagraphStyle(
                    "ib", fontName="Helvetica", fontSize=8, textColor=MID, alignment=TA_RIGHT
                ),
            )
        )
    inc_cells.append(
        Paragraph(
            _fmt_num(sum(data["income_by_month"], Decimal(0))),
            ParagraphStyle(
                "ib2", fontName="Helvetica", fontSize=8, textColor=MID, alignment=TA_RIGHT
            ),
        )
    )
    rows.append(inc_cells)

    total_idx = len(rows) - 2
    tbl = Table(rows, colWidths=CW_t, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
                ("LINEABOVE", (0, total_idx), (-1, total_idx), 1.0, DARK),
                ("BACKGROUND", (0, total_idx), (-1, total_idx), TOTAL_BG),
                ("FONTNAME", (0, total_idx), (-1, total_idx), "Helvetica-Bold"),
                ("LINEABOVE", (0, total_idx + 1), (-1, total_idx + 1), 0.5, RULE),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ]
        )
    )
    story.append(tbl)

    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            t("pdf.expense_trend_note"),
            st["small"],
        )
    )

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 8 — Tagged Transactions Report
# ═══════════════════════════════════════════════════


def _render_legacy_tagged_report(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]
    tags = data["tags"]
    logic = t("pdf.tagged_all_logic") if data["match_all"] else t("pdf.tagged_any_logic")
    tag_label = "  ·  ".join(f"[{t}]" for t in tags)

    fn = _page_fn(owner, t("titles.tagged_report"), period)
    doc = _doc(output_path, fn)
    story = []

    # ═══ PAGE 1 — Transaction list
    story += _page_title_block(
        t("titles.tagged_report"),
        owner,
        period,
        t("pdf.tagged_filter_label").format(tag_label=tag_label, logic=logic),
        st,
    )

    story.append(
        Paragraph(
            t("pdf.tagged_filter_note").format(logic=logic, tags=", ".join(tags)), st["small"]
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    if not data["rows"]:
        story.append(Paragraph(t("pdf.no_transactions_tagged"), st["cell_l"]))
        doc.build(story)
        return

    # Columns: date | description | type | category | tag | amount | running balance
    CW = [2.1 * cm, 5.5 * cm, 2.0 * cm, 3.2 * cm, 2.5 * cm, 2.6 * cm]

    hdr = [
        [
            Paragraph(t("common.date"), st["col_header_l"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.type"), st["col_header"]),
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.running_balance"), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)

    for r in data["rows"]:
        amt = r["amount"]
        desc = r["description"][:48] + "…" if len(r["description"]) > 48 else r["description"]
        cat = r["category"][:26] + "…" if len(r["category"]) > 26 else r["category"]
        rows_tbl.append(
            [
                Paragraph(r["date"], st["cell_l"]),
                Paragraph(desc, st["cell_l"]),
                Paragraph(r["type"][:3].upper(), st["cell_r"]),
                Paragraph(cat, st["cell_l"]),
                Paragraph(_fmt_num(amt, parens_neg=True), st["cell_r"]),
                Paragraph(_fmt_num(r["running_balance"], parens_neg=True), st["cell_r"]),
            ]
        )

    # Total row
    rows_tbl.append(
        [
            Paragraph("", st["cell_l"]),
            Paragraph(t("pdf.total_net_filtered"), st["total_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_l"]),
            Paragraph(
                _fmt_num(data["net"], show_sym=True, sym=sym, parens_neg=True), st["total_r"]
            ),
            Paragraph("", st["cell_r"]),
        ]
    )
    grand_idx = len(rows_tbl) - 1

    tbl = Table(rows_tbl, colWidths=CW, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
                ("FONTSIZE", (0, 1), (-1, -2), 8),
                ("LINEABOVE", (0, grand_idx), (-1, grand_idx), 1.0, DARK),
                ("LINEBELOW", (0, grand_idx), (-1, grand_idx), 0.5, DARK),
                ("BACKGROUND", (0, grand_idx), (-1, grand_idx), TOTAL_BG),
                ("FONTNAME", (0, grand_idx), (-1, grand_idx), "Helvetica-Bold"),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        Paragraph(
            t("pdf.tagged_legend"),
            st["small"],
        )
    )

    # ═══ PAGE 2 — Breakdown by category
    story.append(PageBreak())
    story += _page_title_block(
        t("titles.tagged_report"),
        owner,
        period,
        t("pdf.tagged_section2").format(tag_label=tag_label),
        st,
    )

    CW2 = [10.5 * cm, 3.5 * cm, 3.9 * cm]

    # Income
    if data["income_by_cat"]:
        story.append(Paragraph(t("common.income").upper(), st["section"]))
        hdr_i = [
            [
                Paragraph(t("common.category"), st["col_header_l"]),
                Paragraph(t("common.amount"), st["col_header"]),
                Paragraph(t("common.share"), st["col_header"]),
            ]
        ]
        rows_i = list(hdr_i)
        for i, r in enumerate(data["income_by_cat"]):
            rows_i.append(
                [
                    Paragraph(r["category"], st["cell_l_ind"]),
                    Paragraph(_fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                    Paragraph(f"{r['pct']} %", st["cell_r"]),
                ]
            )
        rows_i.append(
            [
                Paragraph(t("common.total_income"), st["total_l"]),
                Paragraph(_fmt_num(data["total_in"], show_sym=True, sym=sym), st["total_r"]),
                Paragraph("100,0 %" if i18n.CURRENT_LANG == "it" else "100.0 %", st["total_r"]),
            ]
        )
        story.append(_accounting_table(rows_i, CW2, total_rows=[len(rows_i) - 1]))
        story.append(Spacer(1, 0.6 * cm))

    # Expenses
    if data["expense_by_cat"]:
        story.append(Paragraph(t("common.expense").upper(), st["section"]))
        hdr_e = [
            [
                Paragraph(t("common.category"), st["col_header_l"]),
                Paragraph(t("common.amount"), st["col_header"]),
                Paragraph(t("common.share"), st["col_header"]),
            ]
        ]
        rows_e = list(hdr_e)
        for i, r in enumerate(data["expense_by_cat"]):
            rows_e.append(
                [
                    Paragraph(r["category"], st["cell_l_ind"]),
                    Paragraph(_fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                    Paragraph(f"{r['pct']} %", st["cell_r"]),
                ]
            )
        rows_e.append(
            [
                Paragraph(t("common.total_expense"), st["total_l"]),
                Paragraph(_fmt_num(data["total_out"], show_sym=True, sym=sym), st["total_r"]),
                Paragraph("100,0 %" if i18n.CURRENT_LANG == "it" else "100.0 %", st["total_r"]),
            ]
        )
        story.append(_accounting_table(rows_e, CW2, total_rows=[len(rows_e) - 1]))
        story.append(Spacer(1, 0.5 * cm))

    # Final summary
    story.append(Paragraph(t("pdf.section_summary"), st["section"]))
    CW1 = [13.5 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("pdf.total_income_tagged"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_in"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("pdf.total_expense_tagged"), st["cell_l"]),
            Paragraph(f"({_fmt_num(data['total_out'], show_sym=True, sym=sym)})", st["cell_r"]),
        ],
        [
            Paragraph(t("common.net"), st["grand_l"]),
            Paragraph(
                _fmt_num(data["net"], show_sym=True, sym=sym, parens_neg=True), st["grand_r"]
            ),
        ],
    ]
    story.append(_accounting_table(sum_rows, CW1, total_rows=[1], grand_rows=[2]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 9 — Budget vs. Actual
# ═══════════════════════════════════════════════════


def _render_legacy_budget_vs_actual(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.budget_vs_actual_report"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.budget_vs_actual_report"),
        data["owner"],
        period,
        t("pdf.subtitle_budget"),
        st,
    )

    CW = [6.5 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm]

    hdr = [
        [
            Paragraph(t("common.budget"), st["col_header_l"]),
            Paragraph(t("common.limit"), st["col_header"]),
            Paragraph(t("common.actual"), st["col_header"]),
            Paragraph(t("common.variance"), st["col_header"]),
            Paragraph(t("common.variance_pct"), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)

    for i, r in enumerate(data["rows"]):
        is_first = i == 0
        var = r["variance"]
        rows_tbl.append(
            [
                Paragraph(r["budget_name"], st["cell_l"]),
                Paragraph(_fmt_num(r["limit"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(_fmt_num(r["actual"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(_fmt_num(var, parens_neg=True, show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['variance_pct']} %", st["cell_r"]),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("pdf.budgeted_total"), st["total_l"]),
            Paragraph(_fmt_num(data["total_limit"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(_fmt_num(data["total_actual"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(
                _fmt_num(data["total_variance"], parens_neg=True, show_sym=True, sym=sym),
                st["total_r"],
            ),
            Paragraph("", st["cell_r"]),
        ]
    )
    tot_idx = len(rows_tbl) - 1

    tbl = _accounting_table(rows_tbl, CW, total_rows=[tot_idx])
    story.append(tbl)

    if data["unbudgeted_spending"] > 0:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(t("pdf.unbudgeted").upper(), st["section"]))
        ub_rows = [
            [
                Paragraph(t("pdf.unbudgeted"), st["cell_l"]),
                Paragraph(
                    _fmt_num(data["unbudgeted_spending"], show_sym=True, sym=sym), st["cell_r"]
                ),
            ],
        ]
        story.append(_accounting_table(ub_rows, [13.5 * cm, 4.4 * cm]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(t("pdf.expected_note"), st["small"]))

    doc.build(story)


def _render_modern_budget_vs_actual(data: dict[str, Any], output_path: str) -> None:
    """Modern portrait budget analysis with pace tracking."""
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.budget_vs_actual_analysis"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.budget_vs_actual_analysis"), owner, period, t("excel.sheet_budget").upper(), st
    )

    # Budget | Limit | Actual | Variance | Pace
    # Total width = 17.4 cm
    CW = [6.2 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm]

    hdr = [
        [
            Paragraph(t("common.budget"), st["col_header_l"]),
            Paragraph(t("common.limit"), st["col_header"]),
            Paragraph(t("common.actual"), st["col_header"]),
            Paragraph(t("common.variance"), st["col_header"]),
            Paragraph(t("common.pace"), st["col_header"]),
        ]
    ]
    rows = list(hdr)

    for i, r in enumerate(data["rows"]):
        is_first = i == 0

        pace_status = r.get("pace_status", "N/A")
        spent_pct = r.get("spent_pct", Decimal("0"))

        # Color coding for pace
        pace_color_hex = "#1A1A1A"  # DARK
        if pace_status == "AHEAD":
            pace_color_hex = "#c0392b"  # Red (spending too fast)
        elif pace_status == "UNDER":
            pace_color_hex = "#27ae60"  # Green (spending slowly)
        elif pace_status == "ON TRACK":
            pace_color_hex = "#2980b9"  # Blue

        pace_key = f"common.pace_{pace_status.lower().replace(' ', '_').replace('/', '')}"
        pace_label = t(pace_key)
        pace_para = Paragraph(
            f"<font color={pace_color_hex}>{pace_label} ({spent_pct}%)</font>", st["cell_r"]
        )

        rows.append(
            [
                Paragraph(r["budget_name"], st["cell_l"]),
                Paragraph(_fmt_num(r["limit"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(_fmt_num(r["actual"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(
                    _fmt_num(r["variance"], parens_neg=True, show_sym=is_first, sym=sym),
                    st["cell_r"],
                ),
                pace_para,
            ]
        )

    # Totals
    rows.append(
        [
            Paragraph(t("pdf.budgeted_total"), st["total_l"]),
            Paragraph(_fmt_num(data["total_limit"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(_fmt_num(data["total_actual"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(
                _fmt_num(data["total_variance"], parens_neg=True, show_sym=True, sym=sym),
                st["total_r"],
            ),
            Paragraph(f"{data['elapsed_pct']}% ELAPSED", st["cell_r_bold"]),
        ]
    )

    story.append(_accounting_table(rows, CW, total_rows=[len(rows) - 1]))

    if data.get("unbudgeted_spending", 0) > 0:
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph(t("pdf.unbudgeted").upper(), st["section"]))
        ub_rows = [
            [
                Paragraph(t("pdf.unbudgeted"), st["cell_l"]),
                Paragraph(
                    _fmt_num(data["unbudgeted_spending"], show_sym=True, sym=sym), st["cell_r"]
                ),
            ],
        ]
        story.append(_accounting_table(ub_rows, [13.0 * cm, 4.4 * cm]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 10 — Bills & Subscriptions
# ═══════════════════════════════════════════════════


def _render_legacy_bills(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.bills"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.bills"), data["owner"], period, t("pdf.section_bills_sub"), st
    )

    CW = [5.5 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.7 * cm]
    hdr = [
        [
            Paragraph(t("common.name"), st["col_header_l"]),
            Paragraph(t("common.frequency"), st["col_header"]),
            Paragraph(t("common.expected_amount"), st["col_header"]),
            Paragraph(t("common.paid"), st["col_header"]),
            Paragraph(t("excel.col_bills_count"), st["col_header"]),
            Paragraph(t("common.last_payment"), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    for i, r in enumerate(data["rows"]):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(r["name"], st["cell_l"]),
                Paragraph(r["frequency"], st["cell_r"]),
                Paragraph(_fmt_num(r["expected"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(_fmt_num(r["paid_amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(str(r["times_paid"]), st["cell_r"]),
                Paragraph(r["last_paid"] or "—", st["cell_r"]),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("common.total"), st["total_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph(_fmt_num(data["total_expected"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(_fmt_num(data["total_paid"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
        ]
    )
    tot_idx = len(rows_tbl) - 1
    story.append(_accounting_table(rows_tbl, CW, total_rows=[tot_idx]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(t("pdf.expected_note_bills"), st["small"]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 11 — Savings Goals (Piggy Banks)
# ═══════════════════════════════════════════════════


def _render_legacy_savings_goals(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    as_of = _fmt_date(data["as_of_date"])
    sym = data["currency"]
    fn = _page_fn(
        data["owner"],
        t("titles.savings_goals"),
        t("pdf.as_of").format(date=as_of),
        landscape_mode=True,
    )
    doc = _doc(output_path, fn, landscape_mode=True)
    story = []

    story += _page_title_block(
        t("titles.savings_goals"),
        data["owner"],
        t("pdf.as_of").format(date=as_of),
        t("pdf.section_savings_goals"),
        st,
    )

    CW = [5.0 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm]
    hdr = [
        [
            Paragraph(t("common.objective"), st["col_header_l"]),
            Paragraph(t("common.target"), st["col_header"]),
            Paragraph(t("common.reached"), st["col_header"]),
            Paragraph(t("excel.col_savings_remaining").format(sym=sym), st["col_header"]),
            Paragraph(t("excel.col_savings_progress"), st["col_header"]),
            Paragraph(t("excel.col_savings_deadline"), st["col_header"]),
            Paragraph(t("excel.col_savings_monthly").format(sym=sym), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    for i, g in enumerate(data["goals"]):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(g["name"], st["cell_l"]),
                Paragraph(_fmt_num(g["target"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(_fmt_num(g["current"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(_fmt_num(g["remaining"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{g['pct']} %", st["cell_r"]),
                Paragraph(g["target_date"] or "—", st["cell_r"]),
                Paragraph(
                    _fmt_num(g["monthly_needed"], show_sym=is_first, sym=sym)
                    if g["monthly_needed"] > 0
                    else "—",
                    st["cell_r"],
                ),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("pdf.total_goals"), st["total_l"]),
            Paragraph(_fmt_num(data["total_target"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(_fmt_num(data["total_saved"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(
                _fmt_num(data["total_target"] - data["total_saved"], show_sym=True, sym=sym),
                st["total_r"],
            ),
            Paragraph(f"{data['overall_pct']} %", st["total_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
        ]
    )
    tot_idx = len(rows_tbl) - 1
    story.append(_accounting_table(rows_tbl, CW, total_rows=[tot_idx]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(t("pdf.savings_monthly_note"), st["small"]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 12 — Liabilities & Debt
# ═══════════════════════════════════════════════════


def _render_legacy_liabilities(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    as_of = _fmt_date(data["as_of_date"])
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.liabilities"), t("pdf.as_of").format(date=as_of))
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.liabilities"),
        data["owner"],
        t("pdf.as_of").format(date=as_of),
        t("pdf.section_liabilities"),
        st,
    )

    if not data["rows"]:
        story.append(Paragraph(t("pdf.no_liabilities"), st["cell_l"]))
        doc.build(story)
        return

    CW = [5.5 * cm, 2.5 * cm, 2.5 * cm, 2.0 * cm, 2.5 * cm, 2.9 * cm]
    hdr = [
        [
            Paragraph(t("excel.col_liab_name"), st["col_header_l"]),
            Paragraph(t("excel.col_liab_type"), st["col_header"]),
            Paragraph(t("excel.col_liab_balance").format(sym=sym), st["col_header"]),
            Paragraph(t("excel.col_liab_rate"), st["col_header"]),
            Paragraph(t("common.currency_col"), st["col_header"]),
            Paragraph(f"{t('excel.col_liab_payments')[:10]} {period[:7]}–", st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    for i, r in enumerate(data["rows"]):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(r["name"], st["cell_l"]),
                Paragraph(r["type"], st["cell_r"]),
                Paragraph(_fmt_num(r["debt_amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['interest_rate']} %" if r["interest_rate"] else "—", st["cell_r"]),
                Paragraph(r["currency_code"], st["cell_r"]),
                Paragraph(
                    _fmt_num(r["period_payments"], show_sym=is_first, sym=sym)
                    if r["period_payments"]
                    else "—",
                    st["cell_r"],
                ),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("common.total_liabilities"), st["grand_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph(_fmt_num(data["total_debt"], show_sym=True, sym=sym), st["grand_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph(_fmt_num(data["total_payments"], show_sym=True, sym=sym), st["grand_r"]),
        ]
    )
    grand_idx = len(rows_tbl) - 1
    story.append(_accounting_table(rows_tbl, CW, grand_rows=[grand_idx]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(t("pdf.liabilities_note"), st["small"]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 13 — Financial KPI Scorecard
# ═══════════════════════════════════════════════════


def _render_legacy_kpi_scorecard(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.kpi_scorecard"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.kpi_scorecard"), data["owner"], period, t("pdf.section_kpi"), st
    )

    # ── Section 1: Key KPIs in a two-column table
    def _kpi_row(label, value, note=""):
        return [
            Paragraph(label, st["cell_l"]),
            Paragraph(value, st["cell_r"]),
            Paragraph(note, st["small"]),
        ]

    CW_kpi = [7.0 * cm, 4.0 * cm, 6.9 * cm]

    liquidity_str = (
        f"{data['liquidity_ratio']:.2f}x" if data["liquidity_ratio"] is not None else "N/D"
    )

    kpi_rows = [
        [
            Paragraph(t("excel.kpi_indicator"), st["col_header_l"]),
            Paragraph(t("excel.kpi_value"), st["col_header"]),
            Paragraph(t("common.note"), st["col_header_l"]),
        ],
        _kpi_row(
            t("pdf.kpi_savings_rate"), f"{data['savings_rate']} %", t("pdf.kpi_savings_rate_note")
        ),
        _kpi_row(
            t("pdf.kpi_burn_rate"),
            _fmt_num(data["burn_rate"], show_sym=True, sym=sym),
            t("pdf.kpi_burn_rate_note"),
        ),
        _kpi_row(
            t("pdf.kpi_runway"),
            f"{data['cash_runway']} {t('pdf.kpi_runway_unit')}",
            t("pdf.kpi_runway_note"),
        ),
        _kpi_row(
            t("pdf.kpi_net_worth"),
            _fmt_num(data["net_worth"], show_sym=True, sym=sym, parens_neg=True),
            t("pdf.kpi_net_worth_note"),
        ),
        _kpi_row(t("pdf.kpi_liquidity"), liquidity_str, "Liquid Assets / Total Liabilities"),
        _kpi_row(
            t("pdf.kpi_net_cash_flow"),
            _fmt_num(data["net_cash_flow"], show_sym=True, sym=sym, parens_neg=True),
            t("pdf.kpi_net_cash_flow_note"),
        ),
        _kpi_row(
            t("pdf.kpi_avg_monthly_in"),
            _fmt_num(data["avg_monthly_in"], show_sym=True, sym=sym),
            t("pdf.kpi_months_note").format(n_months=data["n_months"]),
        ),
        _kpi_row(
            t("pdf.kpi_avg_monthly_out"),
            _fmt_num(data["avg_monthly_out"], show_sym=True, sym=sym),
            t("pdf.kpi_months_note").format(n_months=data["n_months"]),
        ),
        _kpi_row(t("pdf.kpi_hhi"), f"{data['hhi']:.0f} / 10.000", t("pdf.kpi_hhi_note")),
        _kpi_row(
            t("pdf.kpi_top_client"),
            f"{data['top1_client']} ({data['top1_pct']} %)",
            t("pdf.kpi_top_client_note"),
        ),
    ]

    tbl = _accounting_table(kpi_rows, CW_kpi, total_rows=[])
    story.append(tbl)

    # ── Section 2: Monthly trend
    if data["monthly_trend"]:
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph(t("pdf.trend_monthly"), st["section"]))

        months_abbr = T.get("months_abbr", {})
        CW_t = [3.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm, 3.9 * cm]
        trend_hdr = [
            [
                Paragraph(t("common.month"), st["col_header_l"]),
                Paragraph(t("common.income"), st["col_header"]),
                Paragraph(t("common.expense"), st["col_header"]),
                Paragraph(t("common.net"), st["col_header"]),
                Paragraph(t("common.variation"), st["col_header"]),
            ]
        ]
        trend_rows = list(trend_hdr)
        prev_net = None
        for m in data["monthly_trend"]:
            y, mo = m["month"].split("-")
            label = f"{months_abbr.get(mo, mo)} {y}"
            if prev_net is not None and prev_net != 0:
                var_pct = (m["net"] - prev_net) / abs(prev_net) * 100
                var_str = f"{var_pct:.1f} %"
            else:
                var_str = "—"
            prev_net = m["net"]
            trend_rows.append(
                [
                    Paragraph(label, st["cell_l"]),
                    Paragraph(_fmt_num(m["income"]), st["cell_r"]),
                    Paragraph(_fmt_num(m["expense"]), st["cell_r"]),
                    Paragraph(_fmt_num(m["net"], parens_neg=True), st["cell_r"]),
                    Paragraph(var_str, st["cell_r"]),
                ]
            )
        story.append(_accounting_table(trend_rows, CW_t))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 14 — Year-over-Year Comparison
# ═══════════════════════════════════════════════════


def _render_legacy_yoy(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    sym = data["currency"]
    la = data["period_a"]["label"]
    lb = data["period_b"]["label"]
    fn = _page_fn(data["owner"], t("titles.yoy_comparison"), f"{lb} vs {la}")
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.yoy_comparison"),
        data["owner"],
        f"{lb} vs. {la}",
        t("pdf.section_yoy_comparison"),
        st,
    )

    CW = [6.5 * cm, 2.8 * cm, 2.8 * cm, 2.5 * cm, 2.3 * cm]

    def _section(title, rows_data, total_a, total_b):
        story.append(Paragraph(title, st["section"]))
        hdr = [
            [
                Paragraph(t("common.category"), st["col_header_l"]),
                Paragraph(la, st["col_header"]),
                Paragraph(lb, st["col_header"]),
                Paragraph(t("pdf.delta_absolute"), st["col_header"]),
                Paragraph(t("pdf.delta_pct"), st["col_header"]),
            ]
        ]
        rows_tbl = list(hdr)
        for i, r in enumerate(rows_data):
            is_first = i == 0
            rows_tbl.append(
                [
                    Paragraph(r["category"], st["cell_l_ind"]),
                    Paragraph(_fmt_num(r["amount_a"], show_sym=is_first, sym=sym), st["cell_r"]),
                    Paragraph(_fmt_num(r["amount_b"], show_sym=is_first, sym=sym), st["cell_r"]),
                    Paragraph(
                        _fmt_num(r["delta"], parens_neg=True, show_sym=is_first, sym=sym),
                        st["cell_r"],
                    ),
                    Paragraph(f"{r['delta_pct']} %" if r["amount_b"] else "—", st["cell_r"]),
                ]
            )
        delta_tot = total_a - total_b
        dpct = (delta_tot / total_b * 100).quantize(Decimal("0.1")) if total_b else Decimal("0")
        rows_tbl.append(
            [
                Paragraph(t("common.total"), st["total_l"]),
                Paragraph(_fmt_num(total_a, show_sym=True, sym=sym), st["total_r"]),
                Paragraph(_fmt_num(total_b, show_sym=True, sym=sym), st["total_r"]),
                Paragraph(
                    _fmt_num(delta_tot, parens_neg=True, show_sym=True, sym=sym), st["total_r"]
                ),
                Paragraph(f"{dpct} %", st["total_r"]),
            ]
        )
        story.append(_accounting_table(rows_tbl, CW, total_rows=[len(rows_tbl) - 1]))
        story.append(Spacer(1, 0.5 * cm))

    _section(
        t("pdf.section_income_cat").upper(),
        data["income_rows"],
        data["total_in_a"],
        data["total_in_b"],
    )

    _section(
        t("pdf.section_expense_cat").upper(),
        data["expense_rows"],
        data["total_out_a"],
        data["total_out_b"],
    )

    # Final summary
    story.append(Paragraph(t("common.net").upper(), st["section"]))
    CW_s = [6.5 * cm, 2.8 * cm, 2.8 * cm, 2.5 * cm, 2.3 * cm]
    summary = [
        [
            Paragraph("", st["col_header_l"]),
            Paragraph(la, st["col_header"]),
            Paragraph(lb, st["col_header"]),
            Paragraph(t("pdf.delta_absolute"), st["col_header"]),
            Paragraph(t("pdf.delta_pct"), st["col_header"]),
        ],
        [
            Paragraph(t("common.total_income"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_in_a"], show_sym=True, sym=sym), st["cell_r"]),
            Paragraph(_fmt_num(data["total_in_b"], show_sym=True, sym=sym), st["cell_r"]),
            Paragraph(
                _fmt_num(
                    data["total_in_a"] - data["total_in_b"], parens_neg=True, show_sym=True, sym=sym
                ),
                st["cell_r"],
            ),
            Paragraph(f"{data['delta_in_pct']} %", st["cell_r"]),
        ],
        [
            Paragraph(t("common.total_expense"), st["cell_l"]),
            Paragraph(_fmt_num(data["total_out_a"], show_sym=True, sym=sym), st["cell_r"]),
            Paragraph(_fmt_num(data["total_out_b"], show_sym=True, sym=sym), st["cell_r"]),
            Paragraph(
                _fmt_num(
                    data["total_out_a"] - data["total_out_b"],
                    parens_neg=True,
                    show_sym=True,
                    sym=sym,
                ),
                st["cell_r"],
            ),
            Paragraph(f"{data['delta_out_pct']} %", st["cell_r"]),
        ],
        [
            Paragraph(t("common.net_flow"), st["grand_l"]),
            Paragraph(
                _fmt_num(data["net_a"], parens_neg=True, show_sym=True, sym=sym), st["grand_r"]
            ),
            Paragraph(
                _fmt_num(data["net_b"], parens_neg=True, show_sym=True, sym=sym), st["grand_r"]
            ),
            Paragraph(
                _fmt_num(data["net_a"] - data["net_b"], parens_neg=True, show_sym=True, sym=sym),
                st["grand_r"],
            ),
            Paragraph("", st["cell_r"]),
        ],
    ]
    story.append(_accounting_table(summary, CW_s, total_rows=[2], grand_rows=[3]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(t("pdf.yoy_note").format(la=la, lb=lb), st["small"]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 15 — Cumulative Cash Flow
# ═══════════════════════════════════════════════════


def _render_legacy_cumulative_cashflow(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.cumulative_cash_flow"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.cumulative_cash_flow"), data["owner"], period, t("pdf.section_cumulative_cf"), st
    )

    CW = [3.8 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm, 5.1 * cm]
    hdr = [
        [
            Paragraph(t("common.month"), st["col_header_l"]),
            Paragraph(t("common.income"), st["col_header"]),
            Paragraph(t("common.expense"), st["col_header"]),
            Paragraph(t("excel.col_cumulative_net_month"), st["col_header"]),
            Paragraph(t("excel.col_cumulative_prog"), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    for i, m in enumerate(data["months"]):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(m["month_label"], st["cell_l"]),
                Paragraph(_fmt_num(m["income"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(_fmt_num(m["expense"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(
                    _fmt_num(m["net"], parens_neg=True, show_sym=is_first, sym=sym), st["cell_r"]
                ),
                Paragraph(
                    _fmt_num(m["cumulative"], parens_neg=True, show_sym=is_first, sym=sym),
                    st["cell_r"],
                ),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("pdf.cumulative_final"), st["grand_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph(
                _fmt_num(data["final_cumulative"], parens_neg=True, show_sym=True, sym=sym),
                st["grand_r"],
            ),
        ]
    )
    story.append(_accounting_table(rows_tbl, CW, grand_rows=[len(rows_tbl) - 1]))

    # Notes on peak and low months
    story.append(Spacer(1, 0.5 * cm))
    notes = []
    if data["peak_month"]:
        p = data["peak_month"]
        notes.append(
            t("pdf.cumulative_peak_note").format(
                val=_fmt_num(p["cumulative"], show_sym=True, sym=sym), month=p["month_label"]
            )
        )
    if data["low_month"]:
        low = data["low_month"]
        notes.append(
            t("pdf.cumulative_low_note").format(
                val=_fmt_num(low["cumulative"], parens_neg=True, show_sym=True, sym=sym),
                month=low["month_label"],
            )
        )
    notes.append(t("pdf.cumulative_explanation"))
    story.append(Paragraph("  ".join(notes), st["small"]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 16 — Income Concentration
# ═══════════════════════════════════════════════════


def _render_legacy_income_concentration(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.income_by_client"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.income_by_client"),
        data["owner"],
        period,
        t("pdf.section_income_concentration"),
        st,
    )

    CW = [6.5 * cm, 3.0 * cm, 2.5 * cm, 2.5 * cm, 3.4 * cm]
    hdr = [
        [
            Paragraph(t("common.income_client"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.share"), st["col_header"]),
            Paragraph(t("excel.col_income_conc_count"), st["col_header"]),
            Paragraph(t("excel.col_income_conc_avg").format(sym=sym), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    for i, r in enumerate(data["rows"]):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(r["client"], st["cell_l"]),
                Paragraph(_fmt_num(r["amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['pct']} %", st["cell_r"]),
                Paragraph(str(r["count"]), st["cell_r"]),
                Paragraph(_fmt_num(r["avg_per_tx"], show_sym=is_first, sym=sym), st["cell_r"]),
            ]
        )
    rows_tbl.append(
        [
            Paragraph(t("common.total"), st["total_l"]),
            Paragraph(_fmt_num(data["total_income"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("100,0 %" if i18n.CURRENT_LANG == "it" else "100.0 %", st["total_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
        ]
    )
    story.append(_accounting_table(rows_tbl, CW, total_rows=[len(rows_tbl) - 1]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# DASHBOARD 1 — Income & Expense Dashboard
# ═══════════════════════════════════════════════════


def _render_legacy_income_expense_dashboard(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    fn = _page_fn(data["owner"], t("titles.dashboard_income_expense"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.dashboard_income_expense"), data["owner"], period, t("charts.spending_by_cat"), st
    )

    # Process data for charts
    # Spending by category (top 8)
    exp_rows = data.get("expense_rows") or data.get("expense_by_cat") or []
    exp_data = {r["category"]: float(r["amount"]) for r in exp_rows[:8]}
    if len(exp_rows) > 8:
        others_sum = sum(float(r["amount"]) for r in exp_rows[8:])
        exp_data[t("charts.others")] = others_sum

    pie_buf = create_pie_chart(exp_data, t("charts.spending_by_cat"))

    comp_data = {
        t("charts.income"): float(data["total_income"]),
        t("charts.expense"): float(data["total_expense"]),
    }
    bar_buf = create_bar_chart(comp_data, t("charts.income_vs_expense"))

    row1 = [
        [
            Image(pie_buf, width=8.5 * cm, height=6.5 * cm),
            Image(bar_buf, width=8.5 * cm, height=6.5 * cm),
        ]
    ]
    story.append(Table(row1, colWidths=[9 * cm, 9 * cm]))

    # Top 5 income sources
    income_srcs = data.get("income_by_client") or data.get("income_rows") or []
    src_data = {(r.get("client") or r.get("category")): float(r["amount"]) for r in income_srcs[:5]}
    top5_buf = create_horizontal_bar_chart(src_data, t("charts.top_income_sources"))
    story.append(Spacer(1, 1 * cm))
    story.append(Image(top5_buf, width=17 * cm, height=7 * cm))

    doc.build(story)


# ═══════════════════════════════════════════════════
# DASHBOARD 2 — Financial KPI & Trend Dashboard
# ═══════════════════════════════════════════════════


def _render_legacy_kpi_trend_dashboard(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.dashboard_kpi_trend"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("titles.dashboard_kpi_trend"),
        data["owner"],
        period,
        t("charts.net_cash_flow_trend"),
        st,
    )

    # Monthly trend line chart
    trend_data = {m["month"]: float(m["net"]) for m in data["monthly_trend"]}
    line_buf = create_line_chart(trend_data, t("charts.net_cash_flow_trend"))
    story.append(Image(line_buf, width=17 * cm, height=6 * cm))

    # Net worth area chart (if data available)
    story.append(Spacer(1, 0.5 * cm))
    area_buf = create_area_chart(trend_data, t("charts.net_worth_evolution"))
    story.append(Image(area_buf, width=17 * cm, height=6 * cm))

    # KPI cards as a table
    story.append(Spacer(1, 1 * cm))

    def _card(label, value):
        return [
            Paragraph(f"<b>{label}</b>", st["cell_c"]),
            Paragraph(f"<font size=14 color='#2980b9'>{value}</font>", st["cell_c"]),
        ]

    kpi_row = [
        _card(t("charts.savings_rate_card"), f"{data['savings_rate']}%"),
        _card(t("charts.burn_rate_card"), _fmt_num(data["burn_rate"], sym=sym, show_sym=True)),
        _card(t("charts.runway_card"), f"{data['cash_runway']} {t('pdf.kpi_runway_unit')}"),
    ]

    # Transpose for Table: 2 rows (labels, values) x 3 columns
    tbl_data = [
        [kpi_row[0][0], kpi_row[1][0], kpi_row[2][0]],
        [kpi_row[0][1], kpi_row[1][1], kpi_row[2][1]],
    ]

    story.append(
        Table(
            tbl_data,
            colWidths=[6 * cm, 6 * cm, 6 * cm],
            style=[
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ],
        )
    )

    doc.build(story)


# ═══════════════════════════════════════════════════
# DASHBOARDS — Modern variants
# ═══════════════════════════════════════════════════

# Semantic chart colours (kept in sync with chart_engine)
_C_INCOME = "#2E7D5B"
_C_EXPENSE = "#B3564B"
_C_INK = "#1A1A1A"


def _img(buf, width: float) -> Image:
    """Chart image at a fixed width, aspect ratio preserved."""
    pw, ph = ImageReader(buf).getSize()
    buf.seek(0)
    return Image(buf, width=width, height=width * ph / pw)


def _kpi_strip(cards: list) -> Table:
    """Render a strip of boxed KPI cards.

    Each card is a ``(label, value, value_hex_color)`` tuple.
    """
    n = len(cards)
    gap = 0.4 * cm
    card_w = (17.4 * cm - gap * (n - 1)) / n
    lbl_st = ParagraphStyle(
        "kpi_lbl",
        fontName="Helvetica",
        fontSize=7,
        textColor=LIGHT,
        leading=9,
        alignment=TA_CENTER,
    )
    val_st = ParagraphStyle(
        "kpi_val",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=DARK,
        leading=16,
        alignment=TA_CENTER,
    )

    row: list = []
    widths: list = []
    for i, (label, value, vcolor) in enumerate(cards):
        card = Table(
            [
                [Paragraph(label.upper(), lbl_st)],
                [Paragraph(f"<font color='{vcolor}'>{value}</font>", val_st)],
            ],
            colWidths=[card_w],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), TOTAL_BG),
                    ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (0, 0), 5),
                    ("BOTTOMPADDING", (0, 1), (0, 1), 5),
                ]
            ),
        )
        row.append(card)
        widths.append(card_w)
        if i < n - 1:
            row.append("")
            widths.append(gap)
    return Table([row], colWidths=widths)


def _render_modern_income_expense_dashboard(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.dashboard_income_expense"), period)
    doc = _doc(output_path, fn)
    story: list = []

    story += _page_title_block(
        t("titles.dashboard_income_expense"), data["owner"], period, None, st
    )

    net = data["net_savings"]
    story.append(
        _kpi_strip(
            [
                (
                    t("charts.total_income"),
                    _fmt_num(data["total_income"], sym=sym, show_sym=True),
                    _C_INCOME,
                ),
                (
                    t("charts.total_expense"),
                    _fmt_num(data["total_expense"], sym=sym, show_sym=True),
                    _C_EXPENSE,
                ),
                (
                    t("charts.net_savings"),
                    _fmt_num(net, sym=sym, show_sym=True),
                    _C_INCOME if net >= 0 else _C_EXPENSE,
                ),
                (t("charts.savings_rate_card"), f"{data['savings_rate']}%", _C_INK),
            ]
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    trend = data.get("monthly_trend") or []
    if trend:
        story.append(Paragraph(t("charts.monthly_income_expense").upper(), st["section"]))
        story.append(_img(create_cashflow_combo(trend, ""), 17.2 * cm))
        story.append(Spacer(1, 0.2 * cm))

    exp_rows = data.get("expense_rows") or data.get("expense_by_cat") or []
    exp_data = {r["category"]: float(r["amount"]) for r in exp_rows}
    income_srcs = data.get("income_by_client") or data.get("income_rows") or []
    src_data = {(r.get("client") or r.get("category")): float(r["amount"]) for r in income_srcs[:5]}

    story.append(
        KeepTogether(
            [
                Paragraph(t("charts.spending_by_cat").upper(), st["section"]),
                _img(create_donut_chart(exp_data, ""), 17.2 * cm),
            ]
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        KeepTogether(
            [
                Paragraph(t("charts.top_income_sources").upper(), st["section"]),
                _img(create_horizontal_bar_chart(src_data, ""), 17.2 * cm),
            ]
        )
    )

    doc.build(story)


def _render_modern_kpi_trend_dashboard(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.dashboard_kpi_trend"), period)
    doc = _doc(output_path, fn)
    story: list = []

    story += _page_title_block(t("titles.dashboard_kpi_trend"), data["owner"], period, None, st)

    nw = data.get("net_worth")
    cards = [
        (t("charts.savings_rate_card"), f"{data['savings_rate']}%", _C_INK),
        (
            t("charts.burn_rate_card"),
            _fmt_num(data["burn_rate"], sym=sym, show_sym=True),
            _C_EXPENSE,
        ),
        (
            t("charts.runway_card"),
            f"{data['cash_runway']} {t('pdf.kpi_runway_unit')}",
            _C_INK,
        ),
    ]
    if nw is not None:
        cards.append(
            (
                t("charts.net_worth"),
                _fmt_num(nw, sym=sym, show_sym=True),
                _C_INCOME if nw >= 0 else _C_EXPENSE,
            )
        )
    story.append(_kpi_strip(cards))
    story.append(Spacer(1, 0.4 * cm))

    trend = data.get("monthly_trend") or []
    trend_data = {m["month"]: float(m["net"]) for m in trend}
    story.append(Paragraph(t("charts.net_cash_flow_trend").upper(), st["section"]))
    story.append(_img(create_line_chart(trend_data, ""), 17.2 * cm))

    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(t("charts.cumulative_net").upper(), st["section"]))
    cumulative: dict[str, float] = {}
    running = 0.0
    for m in trend:
        running += float(m["net"])
        cumulative[m["month"]] = running
    story.append(_img(create_area_chart(cumulative, ""), 17.2 * cm))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 17 — Transaction Audit Log
# ═══════════════════════════════════════════════════


def _render_modern_audit_log(data: dict[str, Any], output_path: str) -> None:
    """Technical Audit Log (Modern only)."""
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    owner = data["owner"]

    fn = _page_fn(owner, t("titles.audit_log"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)
    story = []

    story += _page_title_block(
        t("titles.audit_log"),
        owner,
        period,
        t("titles.audit_summary").format(count=data["total_count"]),
        st,
    )

    # Technical Grid
    # ID | Date | Description | Source | Destination | Amount | R | DOC | Audit IDs (Group/Ext)
    CW = [1.6 * cm, 2.0 * cm, 5.0 * cm, 3.5 * cm, 3.5 * cm, 2.2 * cm, 0.6 * cm, 0.8 * cm, 6.9 * cm]

    hdr = [
        [
            Paragraph(t("common.id"), st["col_header_l"]),
            Paragraph(t("common.date"), st["col_header_l"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.source"), st["col_header_l"]),
            Paragraph(t("common.destination"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph("R", st["col_header"]),
            Paragraph(t("reports_extra.col_doc_short"), st["col_header"]),
            Paragraph(t("common.audit_id"), st["col_header_l"]),
        ]
    ]
    rows = list(hdr)

    for r in data["rows"]:
        doc_marker = "[Y]" if r.get("has_attachments") else "[ ]"
        rows.append(
            [
                Paragraph(f"#{r['id']}", st["small"]),
                Paragraph(r["date"], st["cell_l"]),
                Paragraph(r["description"][:50], st["cell_l"]),
                Paragraph(r["source"][:30], st["cell_l_grey"]),
                Paragraph(r["destination"][:30], st["cell_l_grey"]),
                Paragraph(_fmt_num(r["amount"], show_sym=False), st["cell_r"]),
                Paragraph(r["reconciled_tag"], st["cell_c"]),
                Paragraph(doc_marker, st["cell_c"]),
                Paragraph(f"G:{r['group_id']} | E:{r['external_id']}", st["small"]),
            ]
        )

    story.append(
        Table(
            rows,
            colWidths=CW,
            repeatRows=1,
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
                    ("FONTSIZE", (0, 1), (-1, -1), 7),
                ]
            ),
        )
    )

    doc.build(story)


def _render_modern_summary(data: dict[str, Any], output_path: str) -> None:
    """Instance & period summary (Modern only)."""
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = _page_fn(owner, t("titles.summary"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(t("titles.summary"), owner, period, None, st)

    CW = [7.0 * cm, 8.0 * cm]
    inst = data["instance"]
    counts = data["counts"]
    p = data["period"]

    sections = [
        (
            "summary.section_instance",
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
            "summary.section_counts",
            [
                (t("summary.asset_accounts"), str(counts["asset_accounts"])),
                (t("summary.liabilities"), str(counts["liabilities"])),
                (t("summary.budgets"), str(counts["budgets"])),
                (t("summary.bills"), str(counts["bills"])),
                (t("summary.piggy_banks"), str(counts["piggy_banks"])),
            ],
        ),
        (
            "summary.section_period",
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
                (
                    t("summary.avg_daily_income"),
                    _fmt_num(p["avg_daily_income"], show_sym=True, sym=sym),
                ),
                (
                    t("summary.avg_daily_expense"),
                    _fmt_num(p["avg_daily_expense"], show_sym=True, sym=sym),
                ),
            ],
        ),
    ]

    for section_key, items in sections:
        story.append(Paragraph(t(section_key).upper(), st["section"]))
        rows = [
            [Paragraph(label, st["cell_l"]), Paragraph(value or "—", st["cell_r"])]
            for label, value in items
        ]
        story.append(_accounting_table(rows, CW))
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)


def _render_modern_category_ledger(data: dict[str, Any], output_path: str) -> None:
    """Category Detail Ledger (Modern)."""
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = _page_fn(owner, t("reports_extra.section_category_ledger"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(t("reports_extra.section_category_ledger"), owner, period, None, st)

    # date | description | counterpart | amount
    CW = [2.2 * cm, 8.2 * cm, 4.0 * cm, 3.0 * cm]

    for section in data["sections"]:
        story.append(Paragraph(section["category_name"].upper(), st["section"]))

        hdr = [
            [
                Paragraph(t("common.date"), st["col_header_l"]),
                Paragraph(t("common.description"), st["col_header_l"]),
                Paragraph(t("common.counterpart"), st["col_header_l"]),
                Paragraph(t("common.amount"), st["col_header"]),
            ]
        ]
        rows = list(hdr)
        for r in section["rows"]:
            rows.append(
                [
                    Paragraph(r["date"], st["cell_l"]),
                    Paragraph(r["description"], st["cell_l"]),
                    Paragraph(r["counterpart"] or "—", st["cell_l"]),
                    Paragraph(_fmt_num(r["amount"], show_sym=False), st["cell_r"]),
                ]
            )

        rows.append(
            [
                Paragraph(t("common.total"), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(_fmt_num(section["total"], show_sym=True, sym=sym), st["total_r"]),
            ]
        )

        story.append(_accounting_table(rows, CW, total_rows=[len(rows) - 1]))
        story.append(Spacer(1, 0.5 * cm))

    # Grand total if multiple sections
    if len(data["sections"]) > 1:
        story.append(Spacer(1, 0.5 * cm))
        gt_rows = [
            [
                Paragraph(t("common.total").upper(), st["grand_l"]),
                Paragraph(_fmt_num(data["grand_total"], show_sym=True, sym=sym), st["grand_r"]),
            ]
        ]
        story.append(_accounting_table(gt_rows, [14.4 * cm, 3.0 * cm], grand_rows=[0]))

    doc.build(story)


def _render_modern_payee_ledger(data: dict[str, Any], output_path: str) -> None:
    """Payee Detail Ledger (Modern)."""
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = _page_fn(owner, t("reports_extra.section_payee_ledger"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(t("reports_extra.section_payee_ledger"), owner, period, None, st)

    # date | description | category | amount
    CW = [2.2 * cm, 8.2 * cm, 4.0 * cm, 3.0 * cm]

    for section in data["sections"]:
        story.append(Paragraph(section["payee_name"].upper(), st["section"]))

        hdr = [
            [
                Paragraph(t("common.date"), st["col_header_l"]),
                Paragraph(t("common.description"), st["col_header_l"]),
                Paragraph(t("common.category"), st["col_header_l"]),
                Paragraph(t("common.amount"), st["col_header"]),
            ]
        ]
        rows = list(hdr)
        for r in section["rows"]:
            rows.append(
                [
                    Paragraph(r["date"], st["cell_l"]),
                    Paragraph(r["description"], st["cell_l"]),
                    Paragraph(r["category"] or "—", st["cell_l"]),
                    Paragraph(_fmt_num(r["amount"], show_sym=False), st["cell_r"]),
                ]
            )

        rows.append(
            [
                Paragraph(t("common.total"), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(_fmt_num(section["total"], show_sym=True, sym=sym), st["total_r"]),
            ]
        )

        story.append(_accounting_table(rows, CW, total_rows=[len(rows) - 1]))
        story.append(Spacer(1, 0.5 * cm))

    # Grand total if multiple sections
    if len(data["sections"]) > 1:
        story.append(Spacer(1, 0.5 * cm))
        gt_rows = [
            [
                Paragraph(t("common.total").upper(), st["grand_l"]),
                Paragraph(_fmt_num(data["grand_total"], show_sym=True, sym=sym), st["grand_r"]),
            ]
        ]
        story.append(_accounting_table(gt_rows, [14.4 * cm, 3.0 * cm], grand_rows=[0]))

    doc.build(story)


# ═══════════════════════════════════════════════════
# REPORT 18 — Budget Performance Forecast
# ═══════════════════════════════════════════════════


def _render_modern_forecast(data: dict[str, Any], output_path: str) -> None:
    """Budget Performance Forecast (Modern only)."""
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = _page_fn(owner, t("titles.budget_forecast"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)
    story = []

    story += _page_title_block(
        t("titles.budget_forecast"),
        owner,
        period,
        t("pdf.projection_month_end").format(
            elapsed=data["days_elapsed"], total=data["total_days"]
        ),
        st,
    )

    # Budget | Limit | Actual | Daily Avg | Forecast | Variance | Status
    CW = [5.5 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm, 3.5 * cm, 3.5 * cm, 4.6 * cm]

    hdr = [
        [
            Paragraph(t("common.budget"), st["col_header_l"]),
            Paragraph(t("common.limit"), st["col_header"]),
            Paragraph(t("common.actual"), st["col_header"]),
            Paragraph(t("common.daily_avg"), st["col_header"]),
            Paragraph(t("common.forecast"), st["col_header"]),
            Paragraph(t("common.variance"), st["col_header"]),
            Paragraph(t("common.status"), st["col_header"]),
        ]
    ]
    rows = list(hdr)

    for r in data["rows"]:
        status_color = "#27ae60"  # Green
        if r["status"] == "critical":
            status_color = "#c0392b"  # Red
        elif r["status"] == "warning":
            status_color = "#f39c12"  # Orange

        rows.append(
            [
                Paragraph(r["budget_name"], st["cell_l"]),
                Paragraph(_fmt_num(r["limit"], show_sym=False), st["cell_r"]),
                Paragraph(_fmt_num(r["actual"], show_sym=False), st["cell_r"]),
                Paragraph(_fmt_num(r["daily_avg"], show_sym=False), st["cell_r"]),
                Paragraph(f"<b>{_fmt_num(r['forecast'], show_sym=False)}</b>", st["cell_r"]),
                Paragraph(_fmt_num(r["variance"], show_sym=False, parens_neg=True), st["cell_r"]),
                Paragraph(f"<font color={status_color}>{r['status'].upper()}</font>", st["cell_r"]),
            ]
        )

    # Totals
    rows.append(
        [
            Paragraph(t("common.total").upper(), st["total_l"]),
            Paragraph(_fmt_num(data["total_limit"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(_fmt_num(data["total_actual"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph(_fmt_num(data["total_forecast"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(
                _fmt_num(
                    data["total_limit"] - data["total_forecast"],
                    show_sym=True,
                    sym=sym,
                    parens_neg=True,
                ),
                st["total_r"],
            ),
            Paragraph("", st["cell_r"]),
        ]
    )

    story.append(_accounting_table(rows, CW, total_rows=[len(rows) - 1]))

    doc.build(story)


def _render_modern_linkage_audit(data: dict[str, Any], output_path: str) -> None:
    """Linkage & Reimbursement Audit (Modern)."""
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    owner = data["owner"]

    fn = _page_fn(owner, t("pdf.section_linkage_audit"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)
    story = []

    story += _page_title_block(t("pdf.section_linkage_audit"), owner, period, None, st)

    # Date | Description | Category | Link Type | Amount | Linked % | Audit IDs
    CW = [2.2 * cm, 7.6 * cm, 3.6 * cm, 3.6 * cm, 3.0 * cm, 2.5 * cm, 3.6 * cm]

    hdr = [
        [
            Paragraph(t("common.date"), st["col_header_l"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("pdf.col_link_type"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("pdf.col_linked_pct"), st["col_header"]),
            Paragraph(t("common.audit_id"), st["col_header_l"]),
        ]
    ]

    rows = list(hdr)
    total_rows = []

    for group in data["groups"]:
        src = group["source"]
        links = group.get("links", [])

        # Source row (Bold)
        rows.append(
            [
                Paragraph(src["date"], st["cell_l"]),
                Paragraph(f"<b>{src['description']}</b>", st["cell_l"]),
                Paragraph(src.get("category") or "—", st["cell_l"]),
                Paragraph(group.get("link_types") or "—", st["cell_l"]),
                Paragraph(f"<b>{_fmt_num(src['amount'], show_sym=False)}</b>", st["cell_r"]),
                Paragraph("", st["cell_r"]),
                Paragraph(f"S:#{src['id']}", st["small"]),
            ]
        )

        # Links
        total_linked = Decimal("0")
        for lnk in links:
            total_linked += abs(lnk["amount"])
            rows.append(
                [
                    Paragraph(lnk["date"], st["cell_l"]),
                    Paragraph(lnk["description"], st["split_indent"]),
                    Paragraph(lnk.get("category") or "—", st["cell_l"]),
                    Paragraph("", st["cell_l"]),
                    Paragraph(_fmt_num(lnk["amount"], show_sym=False), st["cell_r"]),
                    Paragraph("", st["cell_r"]),
                    Paragraph(f"L:#{lnk['id']}", st["small"]),
                ]
            )

        # Subtotal/linked-% row for the group
        src_amt = abs(src["amount"])
        linked_pct = (
            (total_linked / src_amt * 100).quantize(Decimal("0.1")) if src_amt else Decimal("0")
        )

        rows.append(
            [
                Paragraph("", st["cell_l"]),
                Paragraph(t("pdf.subtotal").format(role=t("pdf.linked_role")), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(_fmt_num(total_linked, show_sym=False), st["total_r"]),
                Paragraph(f"{linked_pct}%", st["total_r"]),
                Paragraph("", st["cell_l"]),
            ]
        )
        total_rows.append(len(rows) - 1)

    story.append(_accounting_table(rows, CW, total_rows=total_rows))
    doc.build(story)


def _render_modern_all_tags(data: dict, path: str) -> None:
    """Comprehensive Tag Ledger (Modern only)."""
    st = _corporate_styles()
    period = _period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = _page_fn(owner, t("pdf.section_all_tags"), period)
    doc = _doc(path, fn)
    story = []

    story += _page_title_block(t("pdf.section_all_tags"), owner, period, None, st)

    # Date | Description | Category | Amount
    CW = [2.5 * cm, 8.4 * cm, 3.5 * cm, 3.0 * cm]

    # data["tags"] is a dict: { tag_name: { "rows": [...], "total": ... } }
    sorted_tags = sorted(data["tags"].items())

    for tag_name, tag_data in sorted_tags:
        story.append(Paragraph(f"TAG: {tag_name}", st["section"]))

        hdr = [
            [
                Paragraph(t("common.date"), st["col_header_l"]),
                Paragraph(t("common.description"), st["col_header_l"]),
                Paragraph(t("common.category"), st["col_header_l"]),
                Paragraph(t("common.amount"), st["col_header"]),
            ]
        ]
        rows = list(hdr)
        for r in tag_data["rows"]:
            rows.append(
                [
                    Paragraph(r["date"], st["cell_l"]),
                    Paragraph(r["description"], st["cell_l"]),
                    Paragraph(r.get("category") or "—", st["cell_l"]),
                    Paragraph(_fmt_num(r["amount"], show_sym=False), st["cell_r"]),
                ]
            )

        rows.append(
            [
                Paragraph(t("common.total"), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(_fmt_num(tag_data["total"], show_sym=True, sym=sym), st["total_r"]),
            ]
        )

        story.append(_accounting_table(rows, CW, total_rows=[len(rows) - 1]))
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)


def _render_modern_historical_report(data: dict[str, Any], output_path: str) -> None:
    """Historical Growth Analysis (Modern)."""
    st = _corporate_styles()
    # Data processor uses 'rows' for years
    years = data["rows"]
    if not years:
        return

    period = f"{years[0]['year']} – {years[-1]['year']}"
    owner = data["owner"]

    fn = _page_fn(owner, t("reports_extra.section_historical_growth"), period)
    doc = _doc(output_path, fn)
    story = []

    story += _page_title_block(
        t("reports_extra.section_historical_growth"), owner, period, None, st
    )

    # Years as columns
    n_years = len(years)

    # Description | Year 1 | Year 2 | ... | Year N
    # Portrait A4 width is 21cm, margins 1.8cm each side -> 17.4cm available
    desc_w = 4.4 * cm
    avail = 17.4 * cm - desc_w
    col_w = avail / n_years
    CW = [desc_w] + [col_w] * n_years

    # Metric Row definition
    def _metric_row(label, key, show_pct=False, is_total=False, calc_savings_rate=False):
        row = [Paragraph(label, st["total_l"] if is_total else st["cell_l"])]
        for y in years:
            if calc_savings_rate:
                inc = Decimal(str(y.get("income", 0)))
                net = Decimal(str(y.get("net", 0)))
                val = (net / inc * 100).quantize(Decimal("0.1")) if inc > 0 else Decimal("0")
            else:
                val = Decimal(str(y.get(key, 0)))

            val_str = f"{val:.1f}%" if show_pct else _fmt_num(val, show_sym=False)
            row.append(Paragraph(val_str, st["total_r"] if is_total else st["cell_r"]))
        return row

    def _delta_row(label, key):
        row = [Paragraph(label, st["small"])]
        for i, y in enumerate(years):
            val = y.get(key, Decimal("0"))
            color = "#27ae60" if val >= 0 else "#c0392b"
            # In data_processor, YoY growth is 0 for the first year
            val_str = f"<font color='{color}'>{val:+.1f}%</font>" if i > 0 else "—"
            row.append(Paragraph(val_str, st["cell_r"]))
        return row

    hdr = [Paragraph("", st["col_header_l"])]
    for y in years:
        hdr.append(Paragraph(str(y["year"]), st["col_header"]))

    rows = [hdr]

    # 1. Income
    rows.append(_metric_row(t("common.total_income"), "income"))
    rows.append(_delta_row(t("pdf.yoy_growth"), "income_growth"))

    # 2. Expenses
    rows.append(_metric_row(t("common.total_expense"), "expense"))
    rows.append(_delta_row(t("pdf.yoy_change"), "expense_growth"))

    # 3. Net Savings
    rows.append(_metric_row(t("common.net_savings"), "net", is_total=True))
    rows.append(_delta_row(t("pdf.yoy_growth"), "net_growth"))

    # 4. Savings Rate
    rows.append(_metric_row(t("common.savings_rate"), None, show_pct=True, calc_savings_rate=True))

    story.append(_accounting_table(rows, CW, total_rows=[5]))

    # Footnote
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            t("pdf.yoy_growth_note"),
            st["small"],
        )
    )

    doc.build(story)


def _render_modern_liquidity_forecast(data: dict[str, Any], output_path: str) -> None:
    """Proactive Liquidity Forecast (Modern)."""
    st = _corporate_styles()
    # Data processor uses 'forecast_months'
    months = data["forecast_months"]
    if not months:
        return

    period = f"{months[0]['month_label']} – {months[-1]['month_label']}"
    owner = data["owner"]

    fn = _page_fn(owner, t("reports_extra.section_liquidity_forecast"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)
    story = []

    story += _page_title_block(
        t("reports_extra.section_liquidity_forecast"), owner, period, None, st
    )

    # 6 Months as columns
    n_months = len(months)

    # Description | M1 | M2 | M3 | M4 | M5 | M6
    # Landscape A4 width is 29.7cm, margins 1.8cm each side -> 26.1cm available
    desc_w = 6.0 * cm
    avail = 26.1 * cm - desc_w
    col_w = avail / n_months
    CW = [desc_w] + [col_w] * n_months

    def _proj_row(label, key, style_key="cell_l", val_style_key="cell_r", calc_net=False):
        row = [Paragraph(label, st[style_key])]
        for m in months:
            if calc_net:
                val = m.get("inflow", Decimal("0")) - m.get("outflow", Decimal("0"))
            else:
                val = m.get(key, Decimal("0"))
            row.append(Paragraph(_fmt_num(val, show_sym=False), st[val_style_key]))
        return row

    hdr = [Paragraph(t("common.category_item"), st["col_header_l"])]
    for m in months:
        hdr.append(Paragraph(m["month_label"], st["col_header"]))

    rows = [hdr]

    # 1. Inflows
    rows.append([Paragraph(t("reports_extra.projected_inflows"), st["section"])])
    rows.append(_proj_row(t("common.income"), "inflow", "cell_l_ind"))

    # 2. Outflows
    rows.append([Paragraph(t("reports_extra.projected_outflows"), st["section"])])
    rows.append(_proj_row(t("common.budget"), "fixed_outflow", "cell_l_ind"))
    rows.append(_proj_row(t("common.expense"), "variable_outflow", "cell_l_ind"))

    # 3. Net Flow
    rows.append(_proj_row(t("common.net_flow"), None, "total_l", "total_r", calc_net=True))

    # 4. Projected Balance
    rows.append(
        _proj_row(t("reports_extra.col_projected_balance"), "balance", "grand_l", "grand_r")
    )

    story.append(
        _accounting_table(rows, CW, total_rows=[len(rows) - 2], grand_rows=[len(rows) - 1])
    )

    # Footnote
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            t("pdf.liquidity_forecast_note"),
            st["small"],
        )
    )

    doc.build(story)


# ═══════════════════════════════════════════════════
# General Journal (Libro Giornale, R-ITA-06) — Modern only, landscape
# ═══════════════════════════════════════════════════


def _render_modern_journal(data: dict[str, Any], output_path: str) -> None:
    st = _styles()
    period = _period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = _page_fn(data["owner"], t("titles.journal"), period, landscape_mode=True)
    doc = _doc(output_path, fn, landscape_mode=True)
    story = []

    story += _page_title_block(
        t("titles.journal"), data["owner"], period, t("pdf.section_journal"), st
    )

    daily = {d["date"]: d for d in data["daily_totals"]}

    # Landscape A4: 26.1 cm available
    CW = [1.2 * cm, 2.2 * cm, 8.9 * cm, 7.8 * cm, 3.0 * cm, 3.0 * cm]
    hdr = [
        [
            Paragraph(t("pdf.journal_col_n"), st["col_header"]),
            Paragraph(t("common.date"), st["col_header"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.account"), st["col_header_l"]),
            Paragraph(t("pdf.journal_debit"), st["col_header"]),
            Paragraph(t("pdf.journal_credit"), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    total_idx_rows: list[int] = []
    rows = data["rows"]
    for i, r in enumerate(rows):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(str(r["n"]) if r["debit"] is not None else "", st["cell_r"]),
                Paragraph(_fmt_date(r["date"]) if r["debit"] is not None else "", st["cell_c"]),
                Paragraph(r["description"], st["cell_l"]),
                Paragraph(r["account"], st["cell_l"]),
                Paragraph(
                    _fmt_num(r["debit"], show_sym=is_first, sym=sym) if r["debit"] else "",
                    st["cell_r"],
                ),
                Paragraph(
                    _fmt_num(r["credit"], show_sym=is_first, sym=sym) if r["credit"] else "",
                    st["cell_r"],
                ),
            ]
        )
        # daily subtotal after the last row of each day
        is_last_of_day = i + 1 == len(rows) or rows[i + 1]["date"] != r["date"]
        if is_last_of_day and r["date"] in daily:
            d = daily[r["date"]]
            rows_tbl.append(
                [
                    Paragraph("", st["total_r"]),
                    Paragraph("", st["total_r"]),
                    Paragraph(
                        t("pdf.journal_daily_total").format(date=_fmt_date(r["date"])),
                        st["total_l"],
                    ),
                    Paragraph("", st["total_r"]),
                    Paragraph(_fmt_num(d["debit"], sym=sym), st["total_r"]),
                    Paragraph(_fmt_num(d["credit"], sym=sym), st["total_r"]),
                ]
            )
            total_idx_rows.append(len(rows_tbl) - 1)

    rows_tbl.append(
        [
            Paragraph("", st["grand_r"]),
            Paragraph("", st["grand_r"]),
            Paragraph(t("common.total"), st["grand_l"]),
            Paragraph("", st["grand_r"]),
            Paragraph(_fmt_num(data["total_debit"], show_sym=True, sym=sym), st["grand_r"]),
            Paragraph(_fmt_num(data["total_credit"], show_sym=True, sym=sym), st["grand_r"]),
        ]
    )
    story.append(
        _accounting_table(rows_tbl, CW, total_rows=total_idx_rows, grand_rows=[len(rows_tbl) - 1])
    )

    doc.build(story)


# ─────────────────────────────────────────────────
# PUBLIC DISPATCHERS (Dual-Mode)
# ─────────────────────────────────────────────────


def render_cash_flow_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_cash_flow(data, path)
    return _render_legacy_cash_flow(data, path)  # TODO: Modern


def render_income_expense_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_income_expense(data, path)
    return _render_legacy_income_expense(data, path)  # TODO: Modern


def render_transaction_register_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_transaction_register(data, path)
    return _render_modern_transaction_register(data, path)


def render_net_worth_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_net_worth(data, path)
    return _render_modern_net_worth(data, path)


def render_account_statements_pdf(data: list, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_account_statements(data, path)
    return _render_legacy_account_statements(data, path)  # TODO: Modern


def render_tax_summary_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_tax_summary(data, path)
    return _render_legacy_tax_summary(data, path)  # TODO: Modern


def render_expense_trend_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_expense_trend(data, path)
    return _render_legacy_expense_trend(data, path)  # TODO: Modern


def render_tagged_report_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_tagged_report(data, path)
    return _render_legacy_tagged_report(data, path)  # TODO: Modern


def render_budget_vs_actual_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_budget_vs_actual(data, path)
    return _render_modern_budget_vs_actual(data, path)


def render_bills_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_bills(data, path)
    return _render_legacy_bills(data, path)  # TODO: Modern


def render_savings_goals_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_savings_goals(data, path)
    return _render_legacy_savings_goals(data, path)  # TODO: Modern


def render_liabilities_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_liabilities(data, path)
    return _render_legacy_liabilities(data, path)  # TODO: Modern


def render_kpi_scorecard_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_kpi_scorecard(data, path)
    return _render_legacy_kpi_scorecard(data, path)  # TODO: Modern


def render_yoy_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_yoy(data, path)
    return _render_legacy_yoy(data, path)  # TODO: Modern


def render_cumulative_cashflow_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_cumulative_cashflow(data, path)
    return _render_legacy_cumulative_cashflow(data, path)  # TODO: Modern


def render_income_concentration_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_income_concentration(data, path)
    return _render_legacy_income_concentration(data, path)  # TODO: Modern


def render_income_expense_dashboard_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_income_expense_dashboard(data, path)
    return _render_modern_income_expense_dashboard(data, path)


def render_kpi_trend_dashboard_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_kpi_trend_dashboard(data, path)
    return _render_modern_kpi_trend_dashboard(data, path)


def render_audit_log_pdf(data: dict, path: str, legacy: bool = False):
    # Audit Log is Modern only
    return _render_modern_audit_log(data, path)


def render_summary_pdf(data: dict, path: str, legacy: bool = False):
    # Summary is Modern only
    return _render_modern_summary(data, path)


def render_forecast_pdf(data: dict, path: str, legacy: bool = False):
    # Forecast is Modern only
    return _render_modern_forecast(data, path)


def render_category_ledger_pdf(data: dict, path: str, legacy: bool = False):
    # Category Ledger is Modern only
    return _render_modern_category_ledger(data, path)


def render_payee_ledger_pdf(data: dict, path: str, legacy: bool = False):
    # Payee Ledger is Modern only
    return _render_modern_payee_ledger(data, path)


def render_linkage_audit_pdf(data: dict, path: str, legacy: bool = False):
    # Linkage Audit is Modern only
    return _render_modern_linkage_audit(data, path)


def render_all_tags_pdf(data: dict, path: str, legacy: bool = False):
    # Tag Ledger is Modern only
    return _render_modern_all_tags(data, path)


def render_historical_report_pdf(data: dict, path: str, legacy: bool = False):
    # Historical report is Modern only
    return _render_modern_historical_report(data, path)


def render_liquidity_forecast_pdf(data: dict, path: str, legacy: bool = False):
    # Liquidity forecast is Modern only
    return _render_modern_liquidity_forecast(data, path)


def render_journal_pdf(data: dict, path: str, legacy: bool = False):
    # General Journal is Modern only
    return _render_modern_journal(data, path)
