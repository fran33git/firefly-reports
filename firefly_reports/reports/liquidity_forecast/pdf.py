"""PDF renderers of the liquidity_forecast report."""

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


def _render_modern_liquidity_forecast(data: dict[str, Any], output_path: str) -> None:
    """Proactive Liquidity Forecast (Modern)."""
    st = corporate_styles()
    # Data processor uses 'forecast_months'
    months = data["forecast_months"]
    if not months:
        return

    period = f"{months[0]['month_label']} – {months[-1]['month_label']}"
    owner = data["owner"]

    fn = page_decorator(
        owner, t("reports_extra.section_liquidity_forecast"), period, landscape_mode=True
    )
    doc = make_doc(output_path, fn, landscape_mode=True)
    story = []

    story += title_block(t("reports_extra.section_liquidity_forecast"), owner, period, None, st)

    # 6 Months as columns
    n_months = len(months)

    # Description | M1 | M2 | M3 | M4 | M5 | M6
    # Landscape A4 width is 29.7cm, margins 1.8cm each side -> 26.1cm available
    desc_w = 6.0 * cm
    avail = 26.1 * cm - desc_w
    col_w = avail / n_months
    CW = [desc_w] + [col_w] * n_months

    def _proj_row(label, key, style_key="cell_l", val_style_key="cell_r", calc_net=False):
        row = [Paragraph(label, st[style_key])]
        for m in months:
            if calc_net:
                val = m.get("inflow", Decimal("0")) - m.get("outflow", Decimal("0"))
            else:
                val = m.get(key, Decimal("0"))
            row.append(Paragraph(fmt_num(val, show_sym=False), st[val_style_key]))
        return row

    hdr = [Paragraph(t("common.category_item"), st["col_header_l"])]
    for m in months:
        hdr.append(Paragraph(m["month_label"], st["col_header"]))

    rows = [hdr]

    # 1. Inflows
    rows.append([Paragraph(t("reports_extra.projected_inflows"), st["section"])])
    rows.append(_proj_row(t("common.income"), "inflow", "cell_l_ind"))

    # 2. Outflows
    rows.append([Paragraph(t("reports_extra.projected_outflows"), st["section"])])
    rows.append(_proj_row(t("common.budget"), "fixed_outflow", "cell_l_ind"))
    rows.append(_proj_row(t("common.expense"), "variable_outflow", "cell_l_ind"))

    # 3. Net Flow
    rows.append(_proj_row(t("common.net_flow"), None, "total_l", "total_r", calc_net=True))

    # 4. Projected Balance
    rows.append(
        _proj_row(t("reports_extra.col_projected_balance"), "balance", "grand_l", "grand_r")
    )

    story.append(accounting_table(rows, CW, total_rows=[len(rows) - 2], grand_rows=[len(rows) - 1]))

    # Footnote
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            t("pdf.liquidity_forecast_note"),
            st["small"],
        )
    )

    doc.build(story)


def render_liquidity_forecast_pdf(data: dict, path: str, legacy: bool = False):
    # Liquidity forecast is Modern only
    return _render_modern_liquidity_forecast(data, path)
