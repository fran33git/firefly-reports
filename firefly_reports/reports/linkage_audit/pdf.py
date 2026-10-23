"""PDF renderers of the linkage_audit report."""

from decimal import Decimal
from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
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


def _render_modern_linkage_audit(data: dict[str, Any], output_path: str) -> None:
    """Linkage & Reimbursement Audit (Modern)."""
    st = corporate_styles()
    period = period_str(data["period_start"], data["period_end"])
    owner = data["owner"]

    fn = page_decorator(owner, t("pdf.section_linkage_audit"), period, landscape_mode=True)
    doc = make_doc(output_path, fn, landscape_mode=True)
    story = []

    story += title_block(t("pdf.section_linkage_audit"), owner, period, None, st)

    # Date | Description | Category | Link Type | Amount | Linked % | Audit IDs
    CW = [2.2 * cm, 7.6 * cm, 3.6 * cm, 3.6 * cm, 3.0 * cm, 2.5 * cm, 3.6 * cm]

    hdr = [
        [
            Paragraph(t("common.date"), st["col_header_l"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("pdf.col_link_type"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("pdf.col_linked_pct"), st["col_header"]),
            Paragraph(t("common.audit_id"), st["col_header_l"]),
        ]
    ]

    rows = list(hdr)
    total_rows = []

    for group in data["groups"]:
        src = group["source"]
        links = group.get("links", [])

        # Source row (Bold)
        rows.append(
            [
                Paragraph(src["date"], st["cell_l"]),
                Paragraph(f"<b>{src['description']}</b>", st["cell_l"]),
                Paragraph(src.get("category") or "—", st["cell_l"]),
                Paragraph(group.get("link_types") or "—", st["cell_l"]),
                Paragraph(f"<b>{fmt_num(src['amount'], show_sym=False)}</b>", st["cell_r"]),
                Paragraph("", st["cell_r"]),
                Paragraph(f"S:#{src['id']}", st["small"]),
            ]
        )

        # Links
        total_linked = Decimal("0")
        for lnk in links:
            total_linked += abs(lnk["amount"])
            rows.append(
                [
                    Paragraph(lnk["date"], st["cell_l"]),
                    Paragraph(lnk["description"], st["split_indent"]),
                    Paragraph(lnk.get("category") or "—", st["cell_l"]),
                    Paragraph("", st["cell_l"]),
                    Paragraph(fmt_num(lnk["amount"], show_sym=False), st["cell_r"]),
                    Paragraph("", st["cell_r"]),
                    Paragraph(f"L:#{lnk['id']}", st["small"]),
                ]
            )

        # Subtotal/linked-% row for the group
        src_amt = abs(src["amount"])
        linked_pct = (
            (total_linked / src_amt * 100).quantize(Decimal("0.1")) if src_amt else Decimal("0")
        )

        rows.append(
            [
                Paragraph("", st["cell_l"]),
                Paragraph(t("pdf.subtotal").format(role=t("pdf.linked_role")), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph(fmt_num(total_linked, show_sym=False), st["total_r"]),
                Paragraph(f"{linked_pct}%", st["total_r"]),
                Paragraph("", st["cell_l"]),
            ]
        )
        total_rows.append(len(rows) - 1)

    story.append(accounting_table(rows, CW, total_rows=total_rows))
    doc.build(story)


def render_linkage_audit_pdf(data: dict, path: str, legacy: bool = False) -> None:
    # Linkage Audit is Modern only
    return _render_modern_linkage_audit(data, path)
