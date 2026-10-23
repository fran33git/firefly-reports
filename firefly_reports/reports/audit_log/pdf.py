"""PDF renderers of the audit_log report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Table,
    TableStyle,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.palette import (
    RULE,
)
from firefly_reports.render.pdf.styles import corporate_styles

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_modern_audit_log(data: dict[str, Any], output_path: str) -> None:
    """Technical Audit Log (Modern only)."""
    st = corporate_styles()
    period = period_str(data["period_start"], data["period_end"])
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.audit_log"), period, landscape_mode=True)
    doc = make_doc(output_path, fn, landscape_mode=True)
    story = []

    story += title_block(
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
                Paragraph(fmt_num(r["amount"], show_sym=False), st["cell_r"]),
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


def render_audit_log_pdf(data: dict, path: str, legacy: bool = False):
    # Audit Log is Modern only
    return _render_modern_audit_log(data, path)
