"""PDF renderers of the payee_ledger report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import corporate_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_modern_payee_ledger(data: dict[str, Any], output_path: str) -> None:
    """Payee Detail Ledger (Modern)."""
    st = corporate_styles()
    period = period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = page_decorator(owner, t("reports_extra.section_payee_ledger"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(t("reports_extra.section_payee_ledger"), owner, period, None, st)

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
                    Paragraph(fmt_num(r["amount"], show_sym=False), st["cell_r"]),
                ]
            )

        rows.append(
            [
                Paragraph(t("common.total"), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(fmt_num(section["total"], show_sym=True, sym=sym), st["total_r"]),
            ]
        )

        story.append(accounting_table(rows, CW, total_rows=[len(rows) - 1]))
        story.append(Spacer(1, 0.5 * cm))

    # Grand total if multiple sections
    if len(data["sections"]) > 1:
        story.append(Spacer(1, 0.5 * cm))
        gt_rows = [
            [
                Paragraph(t("common.total").upper(), st["grand_l"]),
                Paragraph(fmt_num(data["grand_total"], show_sym=True, sym=sym), st["grand_r"]),
            ]
        ]
        story.append(accounting_table(gt_rows, [14.4 * cm, 3.0 * cm], grand_rows=[0]))

    doc.build(story)


def render_payee_ledger_pdf(data: dict, path: str, legacy: bool = False):
    # Payee Ledger is Modern only
    return _render_modern_payee_ledger(data, path)
