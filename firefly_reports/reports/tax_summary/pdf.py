"""PDF renderers of the tax_summary report."""

from decimal import Decimal
from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Spacer,
)

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_tax_summary(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period_label = t("pdf.fiscal_year").format(year=data["year"])
    sym = data["currency"]
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.tax_summary"), period_label)
    doc = make_doc(output_path, fn)
    story = []

    # ═══ PAGE 1 — Professional income
    story += title_block(
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
                Paragraph(fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                Paragraph(f"{pct} %", st["cell_r"]),
            ]
        )
    rows_c.append(
        [
            Paragraph(t("common.total_income"), st["total_l"]),
            Paragraph(fmt_num(total_in, show_sym=True, sym=sym), st["total_r"]),
            Paragraph("100,0 %" if i18n.current().lang == "it" else "100.0 %", st["total_r"]),
        ]
    )
    story.append(accounting_table(rows_c, CW2, total_rows=[len(rows_c) - 1]))
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
                Paragraph(fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
                Paragraph(f"{pct} %", st["cell_r"]),
            ]
        )
    story.append(accounting_table(rows_cl, CW2, total_rows=[]))

    # ═══ PAGE 2 — Deductible expenses
    story.append(PageBreak())
    story += title_block(
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
                Paragraph(fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
            ]
        )
    rows_d.append(
        [
            Paragraph(t("common.total_deductible"), st["total_l"]),
            Paragraph(fmt_num(data["total_deductible"], show_sym=True, sym=sym), st["total_r"]),
        ]
    )
    story.append(accounting_table(rows_d, CW1, total_rows=[len(rows_d) - 1]))
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
                Paragraph(fmt_num(r["amount"], show_sym=(i == 0), sym=sym), st["cell_r"]),
            ]
        )
    story.append(accounting_table(rows_nd, CW1))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            t("pdf.deductible_note"),
            st["small"],
        )
    )

    # ═══ PAGE 3 — Tax summary
    story.append(PageBreak())
    story += title_block(
        t("titles.tax_summary"), owner, period_label, t("pdf.section_tax_summary"), st
    )

    sum_rows = [
        [
            Paragraph(t("pdf.income_in_period"), st["cell_l"]),
            Paragraph(fmt_num(data["total_income"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("common.total_deductible"), st["cell_l_ind"]),
            Paragraph(
                f"({fmt_num(data['total_deductible'], show_sym=True, sym=sym)})", st["cell_r"]
            ),
        ],
        [
            Paragraph(t("common.taxable_estimate"), st["grand_l"]),
            Paragraph(
                fmt_num(data["taxable_estimate"], show_sym=True, sym=sym, parens_neg=True),
                st["grand_r"],
            ),
        ],
    ]
    story.append(accounting_table(sum_rows, CW1, total_rows=[1], grand_rows=[2]))
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(t("pdf.taxable_note"), st["small"]))

    doc.build(story)


def render_tax_summary_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_tax_summary(data, path)
    return _render_legacy_tax_summary(data, path)  # TODO: Modern
