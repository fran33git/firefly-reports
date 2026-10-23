"""PDF renderers of the all_tags report."""

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


def _render_modern_all_tags(data: dict, path: str) -> None:
    """Comprehensive Tag Ledger (Modern only)."""
    st = corporate_styles()
    period = period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = page_decorator(owner, t("pdf.section_all_tags"), period)
    doc = make_doc(path, fn)
    story = []

    story += title_block(t("pdf.section_all_tags"), owner, period, None, st)

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
                    Paragraph(fmt_num(r["amount"], show_sym=False), st["cell_r"]),
                ]
            )

        rows.append(
            [
                Paragraph(t("common.total"), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(fmt_num(tag_data["total"], show_sym=True, sym=sym), st["total_r"]),
            ]
        )

        story.append(accounting_table(rows, CW, total_rows=[len(rows) - 1]))
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)


def render_all_tags_pdf(data: dict, path: str, legacy: bool = False) -> None:
    # Tag Ledger is Modern only
    return _render_modern_all_tags(data, path)
