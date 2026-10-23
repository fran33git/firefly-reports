"""PDF renderers of the historical_growth report."""

from decimal import Decimal
from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import corporate_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_modern_historical_report(data: dict[str, Any], output_path: str) -> None:
    """Historical Growth Analysis (Modern)."""
    st = corporate_styles()
    # Data processor uses 'rows' for years
    years = data["rows"]
    if not years:
        return

    period = f"{years[0]['year']} – {years[-1]['year']}"
    owner = data["owner"]

    fn = page_decorator(owner, t("reports_extra.section_historical_growth"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(t("reports_extra.section_historical_growth"), owner, period, None, st)

    # Years as columns
    n_years = len(years)

    # Description | Year 1 | Year 2 | ... | Year N
    # Portrait A4 width is 21cm, margins 1.8cm each side -> 17.4cm available
    desc_w = 4.4 * cm
    avail = 17.4 * cm - desc_w
    col_w = avail / n_years
    CW = [desc_w] + [col_w] * n_years

    # Metric Row definition
    def _metric_row(label, key, show_pct=False, is_total=False, calc_savings_rate=False):
        row = [Paragraph(label, st["total_l"] if is_total else st["cell_l"])]
        for y in years:
            if calc_savings_rate:
                inc = Decimal(str(y.get("income", 0)))
                net = Decimal(str(y.get("net", 0)))
                val = (net / inc * 100).quantize(Decimal("0.1")) if inc > 0 else Decimal("0")
            else:
                val = Decimal(str(y.get(key, 0)))

            val_str = f"{val:.1f}%" if show_pct else fmt_num(val, show_sym=False)
            row.append(Paragraph(val_str, st["total_r"] if is_total else st["cell_r"]))
        return row

    def _delta_row(label, key):
        row = [Paragraph(label, st["small"])]
        for i, y in enumerate(years):
            val = y.get(key, Decimal("0"))
            color = "#27ae60" if val >= 0 else "#c0392b"
            # In data_processor, YoY growth is 0 for the first year
            val_str = f"<font color='{color}'>{val:+.1f}%</font>" if i > 0 else "—"
            row.append(Paragraph(val_str, st["cell_r"]))
        return row

    hdr = [Paragraph("", st["col_header_l"])]
    for y in years:
        hdr.append(Paragraph(str(y["year"]), st["col_header"]))

    rows = [hdr]

    # 1. Income
    rows.append(_metric_row(t("common.total_income"), "income"))
    rows.append(_delta_row(t("pdf.yoy_growth"), "income_growth"))

    # 2. Expenses
    rows.append(_metric_row(t("common.total_expense"), "expense"))
    rows.append(_delta_row(t("pdf.yoy_change"), "expense_growth"))

    # 3. Net Savings
    rows.append(_metric_row(t("common.net_savings"), "net", is_total=True))
    rows.append(_delta_row(t("pdf.yoy_growth"), "net_growth"))

    # 4. Savings Rate
    rows.append(_metric_row(t("common.savings_rate"), None, show_pct=True, calc_savings_rate=True))

    story.append(accounting_table(rows, CW, total_rows=[5]))

    # Footnote
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            t("pdf.yoy_growth_note"),
            st["small"],
        )
    )

    doc.build(story)


def render_historical_report_pdf(data: dict, path: str, legacy: bool = False):
    # Historical report is Modern only
    return _render_modern_historical_report(data, path)
