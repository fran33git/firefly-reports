"""PDF renderers of the budget_forecast report."""

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


def _render_modern_forecast(data: dict[str, Any], output_path: str) -> None:
    """Budget Performance Forecast (Modern only)."""
    st = corporate_styles()
    period = period_str(data["period_start"], data["period_end"])
    owner = data["owner"]
    sym = data["currency"]

    fn = page_decorator(owner, t("titles.budget_forecast"), period, landscape_mode=True)
    doc = make_doc(output_path, fn, landscape_mode=True)
    story = []

    story += title_block(
        t("titles.budget_forecast"),
        owner,
        period,
        t("pdf.projection_month_end").format(
            elapsed=data["days_elapsed"], total=data["total_days"]
        ),
        st,
    )

    # Budget | Limit | Actual | Daily Avg | Forecast | Variance | Status
    CW = [5.5 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm, 3.5 * cm, 3.5 * cm, 4.6 * cm]

    hdr = [
        [
            Paragraph(t("common.budget"), st["col_header_l"]),
            Paragraph(t("common.limit"), st["col_header"]),
            Paragraph(t("common.actual"), st["col_header"]),
            Paragraph(t("common.daily_avg"), st["col_header"]),
            Paragraph(t("common.forecast"), st["col_header"]),
            Paragraph(t("common.variance"), st["col_header"]),
            Paragraph(t("common.status"), st["col_header"]),
        ]
    ]
    rows = list(hdr)

    for r in data["rows"]:
        status_color = "#27ae60"  # Green
        if r["status"] == "critical":
            status_color = "#c0392b"  # Red
        elif r["status"] == "warning":
            status_color = "#f39c12"  # Orange

        rows.append(
            [
                Paragraph(r["budget_name"], st["cell_l"]),
                Paragraph(fmt_num(r["limit"], show_sym=False), st["cell_r"]),
                Paragraph(fmt_num(r["actual"], show_sym=False), st["cell_r"]),
                Paragraph(fmt_num(r["daily_avg"], show_sym=False), st["cell_r"]),
                Paragraph(f"<b>{fmt_num(r['forecast'], show_sym=False)}</b>", st["cell_r"]),
                Paragraph(fmt_num(r["variance"], show_sym=False, parens_neg=True), st["cell_r"]),
                Paragraph(f"<font color={status_color}>{r['status'].upper()}</font>", st["cell_r"]),
            ]
        )

    # Totals
    rows.append(
        [
            Paragraph(t("common.total").upper(), st["total_l"]),
            Paragraph(fmt_num(data["total_limit"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(fmt_num(data["total_actual"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph("", st["cell_r"]),
            Paragraph(fmt_num(data["total_forecast"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(
                fmt_num(
                    data["total_limit"] - data["total_forecast"],
                    show_sym=True,
                    sym=sym,
                    parens_neg=True,
                ),
                st["total_r"],
            ),
            Paragraph("", st["cell_r"]),
        ]
    )

    story.append(accounting_table(rows, CW, total_rows=[len(rows) - 1]))

    doc.build(story)


def render_forecast_pdf(data: dict, path: str, legacy: bool = False) -> None:
    # Forecast is Modern only
    return _render_modern_forecast(data, path)
