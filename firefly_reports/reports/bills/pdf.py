"""PDF renderers of the bills report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_bills(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.bills"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(t("titles.bills"), data["owner"], period, t("pdf.section_bills_sub"), st)

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
                Paragraph(fmt_num(r["expected"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(fmt_num(r["paid_amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(str(r["times_paid"]), st["cell_r"]),
                Paragraph(r["last_paid"] or "—", st["cell_r"]),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("common.total"), st["total_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph(fmt_num(data["total_expected"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(fmt_num(data["total_paid"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
        ]
    )
    tot_idx = len(rows_tbl) - 1
    story.append(accounting_table(rows_tbl, CW, total_rows=[tot_idx]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(t("pdf.expected_note_bills"), st["small"]))

    doc.build(story)


def render_bills_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_bills(data, path)
    return _render_legacy_bills(data, path)  # TODO: Modern
