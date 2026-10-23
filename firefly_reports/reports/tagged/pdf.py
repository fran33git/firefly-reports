"""PDF renderers of the tagged report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.palette import (
    DARK,
    RULE,
    TOTAL_BG,
)
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_tagged_report(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]
    tags = data["tags"]
    logic = t("pdf.tagged_all_logic") if data["match_all"] else t("pdf.tagged_any_logic")
    tag_label = "  ·  ".join(f"[{t}]" for t in tags)

    fn = page_decorator(owner, t("titles.tagged_report"), period)
    doc = make_doc(output_path, fn)
    story = []

    # ═══ PAGE 1 — Transaction list
    story += title_block(
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
                Paragraph(fmt_num(amt, parens_neg=True), st["cell_r"]),
                Paragraph(fmt_num(r["running_balance"], parens_neg=True), st["cell_r"]),
            ]
        )

    # Total row
    rows_tbl.append(
        [
            Paragraph("", st["cell_l"]),
            Paragraph(t("pdf.total_net_filtered"), st["total_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_l"]),
            Paragraph(fmt_num(data["net"], show_sym=True, sym=sym, parens_neg=True), st["total_r"]),
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
    story += title_block(
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
                    Paragraph(fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                    Paragraph(f"{r['pct']} %", st["cell_r"]),
                ]
            )
        rows_i.append(
            [
                Paragraph(t("common.total_income"), st["total_l"]),
                Paragraph(fmt_num(data["total_in"], show_sym=True, sym=sym), st["total_r"]),
                Paragraph("100,0 %" if i18n.current().lang == "it" else "100.0 %", st["total_r"]),
            ]
        )
        story.append(accounting_table(rows_i, CW2, total_rows=[len(rows_i) - 1]))
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
                    Paragraph(fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                    Paragraph(f"{r['pct']} %", st["cell_r"]),
                ]
            )
        rows_e.append(
            [
                Paragraph(t("common.total_expense"), st["total_l"]),
                Paragraph(fmt_num(data["total_out"], show_sym=True, sym=sym), st["total_r"]),
                Paragraph("100,0 %" if i18n.current().lang == "it" else "100.0 %", st["total_r"]),
            ]
        )
        story.append(accounting_table(rows_e, CW2, total_rows=[len(rows_e) - 1]))
        story.append(Spacer(1, 0.5 * cm))

    # Final summary
    story.append(Paragraph(t("pdf.section_summary"), st["section"]))
    CW1 = [13.5 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("pdf.total_income_tagged"), st["cell_l"]),
            Paragraph(fmt_num(data["total_in"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("pdf.total_expense_tagged"), st["cell_l"]),
            Paragraph(f"({fmt_num(data['total_out'], show_sym=True, sym=sym)})", st["cell_r"]),
        ],
        [
            Paragraph(t("common.net"), st["grand_l"]),
            Paragraph(fmt_num(data["net"], show_sym=True, sym=sym, parens_neg=True), st["grand_r"]),
        ],
    ]
    story.append(accounting_table(sum_rows, CW1, total_rows=[1], grand_rows=[2]))

    doc.build(story)


def render_tagged_report_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_tagged_report(data, path)
    return _render_legacy_tagged_report(data, path)  # TODO: Modern
