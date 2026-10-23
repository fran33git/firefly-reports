"""PDF renderers of the savings_goals report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_date, fmt_num
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_savings_goals(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    as_of = fmt_date(data["as_of_date"])
    sym = data["currency"]
    fn = page_decorator(
        data["owner"],
        t("titles.savings_goals"),
        t("pdf.as_of").format(date=as_of),
        landscape_mode=True,
    )
    doc = make_doc(output_path, fn, landscape_mode=True)
    story = []

    story += title_block(
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
                Paragraph(fmt_num(g["target"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(fmt_num(g["current"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(fmt_num(g["remaining"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{g['pct']} %", st["cell_r"]),
                Paragraph(g["target_date"] or "—", st["cell_r"]),
                Paragraph(
                    fmt_num(g["monthly_needed"], show_sym=is_first, sym=sym)
                    if g["monthly_needed"] > 0
                    else "—",
                    st["cell_r"],
                ),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("pdf.total_goals"), st["total_l"]),
            Paragraph(fmt_num(data["total_target"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(fmt_num(data["total_saved"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(
                fmt_num(data["total_target"] - data["total_saved"], show_sym=True, sym=sym),
                st["total_r"],
            ),
            Paragraph(f"{data['overall_pct']} %", st["total_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
        ]
    )
    tot_idx = len(rows_tbl) - 1
    story.append(accounting_table(rows_tbl, CW, total_rows=[tot_idx]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(t("pdf.savings_monthly_note"), st["small"]))

    doc.build(story)


def render_savings_goals_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_savings_goals(data, path)
    return _render_legacy_savings_goals(data, path)  # TODO: Modern
