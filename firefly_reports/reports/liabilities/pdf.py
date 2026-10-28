"""PDF renderers of the liabilities report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
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


def _render_legacy_liabilities(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    as_of = fmt_date(data["as_of_date"])
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.liabilities"), t("pdf.as_of").format(date=as_of))
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
        t("titles.liabilities"),
        data["owner"],
        t("pdf.as_of").format(date=as_of),
        t("pdf.section_liabilities"),
        st,
    )

    if not data["rows"]:
        story.append(Paragraph(t("pdf.no_liabilities"), st["cell_l"]))
        doc.build(story)
        return

    CW = [5.5 * cm, 2.5 * cm, 2.5 * cm, 2.0 * cm, 2.5 * cm, 2.9 * cm]
    hdr = [
        [
            Paragraph(t("excel.col_liab_name"), st["col_header_l"]),
            Paragraph(t("excel.col_liab_type"), st["col_header"]),
            Paragraph(t("excel.col_liab_balance").format(sym=sym), st["col_header"]),
            Paragraph(t("excel.col_liab_rate"), st["col_header"]),
            Paragraph(t("common.currency_col"), st["col_header"]),
            Paragraph(f"{t('excel.col_liab_payments')[:10]} {period[:7]}–", st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)
    for i, r in enumerate(data["rows"]):
        is_first = i == 0
        rows_tbl.append(
            [
                Paragraph(r["name"], st["cell_l"]),
                Paragraph(r["type"], st["cell_r"]),
                Paragraph(fmt_num(r["debt_amount"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['interest_rate']} %" if r["interest_rate"] else "—", st["cell_r"]),
                Paragraph(r["currency_code"], st["cell_r"]),
                Paragraph(
                    fmt_num(r["period_payments"], show_sym=is_first, sym=sym)
                    if r["period_payments"]
                    else "—",
                    st["cell_r"],
                ),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("common.total_liabilities"), st["grand_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph(fmt_num(data["total_debt"], show_sym=True, sym=sym), st["grand_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph(fmt_num(data["total_payments"], show_sym=True, sym=sym), st["grand_r"]),
        ]
    )
    grand_idx = len(rows_tbl) - 1
    story.append(accounting_table(rows_tbl, CW, grand_rows=[grand_idx]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(t("pdf.liabilities_note"), st["small"]))

    doc.build(story)


def render_liabilities_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_liabilities(data, path)
    return _render_legacy_liabilities(data, path)  # TODO: Modern
