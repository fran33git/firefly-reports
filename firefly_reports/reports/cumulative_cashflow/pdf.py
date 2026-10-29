"""PDF renderers of the cumulative_cashflow report."""

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


def _render_legacy_cumulative_cashflow(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.cumulative_cash_flow"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
        t("titles.cumulative_cash_flow"), data["owner"], period, t("pdf.section_cumulative_cf"), st
    )

    CW = [3.8 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm, 5.1 * cm]
    hdr = [
        [
            Paragraph(t("common.month"), st["col_header_l"]),
            Paragraph(t("common.income"), st["col_header"]),
            Paragraph(t("common.expense"), st["col_header"]),
            Paragraph(t("excel.col_cumulative_net_month"), st["col_header"]),
            Paragraph(t("excel.col_cumulative_prog"), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    for i, m in enumerate(data["months"]):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(m["month_label"], st["cell_l"]),
                Paragraph(fmt_num(m["income"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(fmt_num(m["expense"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(
                    fmt_num(m["net"], parens_neg=True, show_sym=is_first, sym=sym), st["cell_r"]
                ),
                Paragraph(
                    fmt_num(m["cumulative"], parens_neg=True, show_sym=is_first, sym=sym),
                    st["cell_r"],
                ),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("pdf.cumulative_final"), st["grand_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph(
                fmt_num(data["final_cumulative"], parens_neg=True, show_sym=True, sym=sym),
                st["grand_r"],
            ),
        ]
    )
    story.append(accounting_table(rows_tbl, CW, grand_rows=[len(rows_tbl) - 1]))

    # Notes on peak and low months
    story.append(Spacer(1, 0.5 * cm))
    notes = []
    if data["peak_month"]:
        p = data["peak_month"]
        notes.append(
            t("pdf.cumulative_peak_note").format(
                val=fmt_num(p["cumulative"], show_sym=True, sym=sym), month=p["month_label"]
            )
        )
    if data["low_month"]:
        low = data["low_month"]
        notes.append(
            t("pdf.cumulative_low_note").format(
                val=fmt_num(low["cumulative"], parens_neg=True, show_sym=True, sym=sym),
                month=low["month_label"],
            )
        )
    notes.append(t("pdf.cumulative_explanation"))
    story.append(Paragraph("  ".join(notes), st["small"]))

    doc.build(story)


def render_cumulative_cashflow_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_cumulative_cashflow(data, path)
    return _render_legacy_cumulative_cashflow(data, path)  # TODO: Modern
