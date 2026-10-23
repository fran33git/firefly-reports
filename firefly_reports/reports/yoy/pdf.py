"""PDF renderers of the yoy report."""

from decimal import Decimal
from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_yoy(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    sym = data["currency"]
    la = data["period_a"]["label"]
    lb = data["period_b"]["label"]
    fn = page_decorator(data["owner"], t("titles.yoy_comparison"), f"{lb} vs {la}")
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
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
                    Paragraph(fmt_num(r["amount_a"], show_sym=is_first, sym=sym), st["cell_r"]),
                    Paragraph(fmt_num(r["amount_b"], show_sym=is_first, sym=sym), st["cell_r"]),
                    Paragraph(
                        fmt_num(r["delta"], parens_neg=True, show_sym=is_first, sym=sym),
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
                Paragraph(fmt_num(total_a, show_sym=True, sym=sym), st["total_r"]),
                Paragraph(fmt_num(total_b, show_sym=True, sym=sym), st["total_r"]),
                Paragraph(
                    fmt_num(delta_tot, parens_neg=True, show_sym=True, sym=sym), st["total_r"]
                ),
                Paragraph(f"{dpct} %", st["total_r"]),
            ]
        )
        story.append(accounting_table(rows_tbl, CW, total_rows=[len(rows_tbl) - 1]))
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
            Paragraph(fmt_num(data["total_in_a"], show_sym=True, sym=sym), st["cell_r"]),
            Paragraph(fmt_num(data["total_in_b"], show_sym=True, sym=sym), st["cell_r"]),
            Paragraph(
                fmt_num(
                    data["total_in_a"] - data["total_in_b"], parens_neg=True, show_sym=True, sym=sym
                ),
                st["cell_r"],
            ),
            Paragraph(f"{data['delta_in_pct']} %", st["cell_r"]),
        ],
        [
            Paragraph(t("common.total_expense"), st["cell_l"]),
            Paragraph(fmt_num(data["total_out_a"], show_sym=True, sym=sym), st["cell_r"]),
            Paragraph(fmt_num(data["total_out_b"], show_sym=True, sym=sym), st["cell_r"]),
            Paragraph(
                fmt_num(
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
                fmt_num(data["net_a"], parens_neg=True, show_sym=True, sym=sym), st["grand_r"]
            ),
            Paragraph(
                fmt_num(data["net_b"], parens_neg=True, show_sym=True, sym=sym), st["grand_r"]
            ),
            Paragraph(
                fmt_num(data["net_a"] - data["net_b"], parens_neg=True, show_sym=True, sym=sym),
                st["grand_r"],
            ),
            Paragraph("", st["cell_r"]),
        ],
    ]
    story.append(accounting_table(summary, CW_s, total_rows=[2], grand_rows=[3]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(t("pdf.yoy_note").format(la=la, lb=lb), st["small"]))

    doc.build(story)


def render_yoy_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_yoy(data, path)
    return _render_legacy_yoy(data, path)  # TODO: Modern
