"""PDF renderers of the income_concentration report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
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


def _render_legacy_income_concentration(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.income_by_client"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
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
                Paragraph(fmt_num(r["amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['pct']} %", st["cell_r"]),
                Paragraph(str(r["count"]), st["cell_r"]),
                Paragraph(fmt_num(r["avg_per_tx"], show_sym=is_first, sym=sym), st["cell_r"]),
            ]
        )
    rows_tbl.append(
        [
            Paragraph(t("common.total"), st["total_l"]),
            Paragraph(fmt_num(data["total_income"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("100,0 %" if i18n.current().lang == "it" else "100.0 %", st["total_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
        ]
    )
    story.append(accounting_table(rows_tbl, CW, total_rows=[len(rows_tbl) - 1]))

    doc.build(story)


def render_income_concentration_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_income_concentration(data, path)
    return _render_legacy_income_concentration(data, path)  # TODO: Modern
