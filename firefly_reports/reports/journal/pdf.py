"""PDF renderers of the journal report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_date, fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_modern_journal(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.journal"), period, landscape_mode=True)
    doc = make_doc(output_path, fn, landscape_mode=True)
    story = []

    story += title_block(t("titles.journal"), data["owner"], period, t("pdf.section_journal"), st)

    daily = {d["date"]: d for d in data["daily_totals"]}

    # Landscape A4: 26.1 cm available
    CW = [1.2 * cm, 2.2 * cm, 8.9 * cm, 7.8 * cm, 3.0 * cm, 3.0 * cm]
    hdr = [
        [
            Paragraph(t("pdf.journal_col_n"), st["col_header"]),
            Paragraph(t("common.date"), st["col_header"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.account"), st["col_header_l"]),
            Paragraph(t("pdf.journal_debit"), st["col_header"]),
            Paragraph(t("pdf.journal_credit"), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    total_idx_rows: list[int] = []
    rows = data["rows"]
    for i, r in enumerate(rows):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(str(r["n"]) if r["debit"] is not None else "", st["cell_r"]),
                Paragraph(fmt_date(r["date"]) if r["debit"] is not None else "", st["cell_c"]),
                Paragraph(r["description"], st["cell_l"]),
                Paragraph(r["account"], st["cell_l"]),
                Paragraph(
                    fmt_num(r["debit"], show_sym=is_first, sym=sym) if r["debit"] else "",
                    st["cell_r"],
                ),
                Paragraph(
                    fmt_num(r["credit"], show_sym=is_first, sym=sym) if r["credit"] else "",
                    st["cell_r"],
                ),
            ]
        )
        # daily subtotal after the last row of each day
        is_last_of_day = i + 1 == len(rows) or rows[i + 1]["date"] != r["date"]
        if is_last_of_day and r["date"] in daily:
            d = daily[r["date"]]
            rows_tbl.append(
                [
                    Paragraph("", st["total_r"]),
                    Paragraph("", st["total_r"]),
                    Paragraph(
                        t("pdf.journal_daily_total").format(date=fmt_date(r["date"])),
                        st["total_l"],
                    ),
                    Paragraph("", st["total_r"]),
                    Paragraph(fmt_num(d["debit"], sym=sym), st["total_r"]),
                    Paragraph(fmt_num(d["credit"], sym=sym), st["total_r"]),
                ]
            )
            total_idx_rows.append(len(rows_tbl) - 1)

    rows_tbl.append(
        [
            Paragraph("", st["grand_r"]),
            Paragraph("", st["grand_r"]),
            Paragraph(t("common.total"), st["grand_l"]),
            Paragraph("", st["grand_r"]),
            Paragraph(fmt_num(data["total_debit"], show_sym=True, sym=sym), st["grand_r"]),
            Paragraph(fmt_num(data["total_credit"], show_sym=True, sym=sym), st["grand_r"]),
        ]
    )
    story.append(
        accounting_table(rows_tbl, CW, total_rows=total_idx_rows, grand_rows=[len(rows_tbl) - 1])
    )

    doc.build(story)


def render_journal_pdf(data: dict, path: str, legacy: bool = False):
    # General Journal is Modern only
    return _render_modern_journal(data, path)
