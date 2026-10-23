"""PDF renderers of the income_expense report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Spacer,
)

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_income_expense(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.income_expense_summary"), period)
    doc = make_doc(output_path, fn)
    story = []

    CW = [10.5 * cm, 3.5 * cm, 3.9 * cm]  # label | amount | % share

    # ═══ PAGE 1 — Income by category
    story += title_block(
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
                Paragraph(fmt_num(r["amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['pct']} %", st["cell_r"]),
            ]
        )
    rows.append(
        [
            Paragraph(t("common.total_income"), st["total_l"]),
            Paragraph(fmt_num(data["total_income"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("100,0 %" if i18n.current().lang == "it" else "100.0 %", st["total_r"]),
        ]
    )
    t_idx = len(rows) - 1
    story.append(accounting_table(rows, CW, total_rows=[t_idx]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(t("pdf.share_note_income"), st["small"]))

    # ═══ PAGE 2 — Expenses by category
    story.append(PageBreak())
    story += title_block(
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
                Paragraph(fmt_num(r["amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['pct']} %", st["cell_r"]),
            ]
        )
    rows2.append(
        [
            Paragraph(t("common.total_expense"), st["total_l"]),
            Paragraph(fmt_num(data["total_expense"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("100,0 %" if i18n.current().lang == "it" else "100.0 %", st["total_r"]),
        ]
    )
    t2_idx = len(rows2) - 1
    story.append(accounting_table(rows2, CW, total_rows=[t2_idx]))
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
                    Paragraph(fmt_num(b["spent"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                ]
            )
        story.append(accounting_table(rows_b, CW_b))
        story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph(t("pdf.share_note"), st["small"]))

    # ═══ PAGE 3 — Summary
    story.append(PageBreak())
    story += title_block(
        t("titles.income_expense_summary"), owner, period, t("pdf.section_summary_analysis"), st
    )

    CW_s = [13.5 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("pdf.total_income_period"), st["cell_l"]),
            Paragraph(fmt_num(data["total_income"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("pdf.total_expense_period"), st["cell_l"]),
            Paragraph(f"({fmt_num(data['total_expense'], show_sym=True, sym=sym)})", st["cell_r"]),
        ],
        [
            Paragraph(t("common.net_savings"), st["grand_l"]),
            Paragraph(
                fmt_num(data["net_savings"], show_sym=True, sym=sym, parens_neg=True),
                st["grand_r"],
            ),
        ],
    ]
    story.append(accounting_table(sum_rows, CW_s, total_rows=[1], grand_rows=[2]))
    story.append(Spacer(1, 0.6 * cm))

    # Savings rate breakdown
    rate_rows = [
        [
            Paragraph(t("common.savings_rate"), st["cell_l"]),
            Paragraph(f"{data['savings_rate']} %", st["cell_r"]),
        ],
        [
            Paragraph(t("common.income"), st["cell_l"]),
            Paragraph(fmt_num(data["total_income"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("common.expense"), st["cell_l"]),
            Paragraph(fmt_num(data["total_expense"], show_sym=True, sym=sym), st["cell_r"]),
        ],
    ]
    story.append(Paragraph(t("pdf.section_indicators"), st["section"]))
    story.append(accounting_table(rate_rows, CW_s))

    doc.build(story)


def render_income_expense_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_income_expense(data, path)
    return _render_legacy_income_expense(data, path)  # TODO: Modern
