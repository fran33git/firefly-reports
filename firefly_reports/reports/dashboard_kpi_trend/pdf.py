"""PDF renderers of the dashboard_kpi_trend report."""

from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    Spacer,
    Table,
)

from firefly_reports.i18n import t
from firefly_reports.render.charts import (
    create_area_chart,
    create_line_chart,
)
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.palette import (
    C_EXPENSE,
    C_INCOME,
    C_INK,
)
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.widgets import chart_image, kpi_strip

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_kpi_trend_dashboard(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.dashboard_kpi_trend"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
        t("titles.dashboard_kpi_trend"),
        data["owner"],
        period,
        t("charts.net_cash_flow_trend"),
        st,
    )

    # Monthly trend line chart
    trend_data = {m["month"]: float(m["net"]) for m in data["monthly_trend"]}
    line_buf = create_line_chart(trend_data, t("charts.net_cash_flow_trend"))
    story.append(Image(line_buf, width=17 * cm, height=6 * cm))

    # Net worth area chart (if data available)
    story.append(Spacer(1, 0.5 * cm))
    area_buf = create_area_chart(trend_data, t("charts.net_worth_evolution"))
    story.append(Image(area_buf, width=17 * cm, height=6 * cm))

    # KPI cards as a table
    story.append(Spacer(1, 1 * cm))

    def _card(label: str, value: Any) -> list[Any]:
        return [
            Paragraph(f"<b>{label}</b>", st["cell_c"]),
            Paragraph(f"<font size=14 color='#2980b9'>{value}</font>", st["cell_c"]),
        ]

    kpi_row = [
        _card(t("charts.savings_rate_card"), f"{data['savings_rate']}%"),
        _card(t("charts.burn_rate_card"), fmt_num(data["burn_rate"], sym=sym, show_sym=True)),
        _card(t("charts.runway_card"), f"{data['cash_runway']} {t('pdf.kpi_runway_unit')}"),
    ]

    # Transpose for Table: 2 rows (labels, values) x 3 columns
    tbl_data = [
        [kpi_row[0][0], kpi_row[1][0], kpi_row[2][0]],
        [kpi_row[0][1], kpi_row[1][1], kpi_row[2][1]],
    ]

    story.append(
        Table(
            tbl_data,
            colWidths=[6 * cm, 6 * cm, 6 * cm],
            style=[
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ],
        )
    )

    doc.build(story)


def _render_modern_kpi_trend_dashboard(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.dashboard_kpi_trend"), period)
    doc = make_doc(output_path, fn)
    story: list = []

    story += title_block(t("titles.dashboard_kpi_trend"), data["owner"], period, None, st)

    nw = data.get("net_worth")
    cards = [
        (t("charts.savings_rate_card"), f"{data['savings_rate']}%", C_INK),
        (
            t("charts.burn_rate_card"),
            fmt_num(data["burn_rate"], sym=sym, show_sym=True),
            C_EXPENSE,
        ),
        (
            t("charts.runway_card"),
            f"{data['cash_runway']} {t('pdf.kpi_runway_unit')}",
            C_INK,
        ),
    ]
    if nw is not None:
        cards.append(
            (
                t("charts.net_worth"),
                fmt_num(nw, sym=sym, show_sym=True),
                C_INCOME if nw >= 0 else C_EXPENSE,
            )
        )
    story.append(kpi_strip(cards))
    story.append(Spacer(1, 0.4 * cm))

    trend = data.get("monthly_trend") or []
    trend_data = {m["month"]: float(m["net"]) for m in trend}
    story.append(Paragraph(t("charts.net_cash_flow_trend").upper(), st["section"]))
    story.append(chart_image(create_line_chart(trend_data, ""), 17.2 * cm))

    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(t("charts.cumulative_net").upper(), st["section"]))
    cumulative: dict[str, float] = {}
    running = 0.0
    for m in trend:
        running += float(m["net"])
        cumulative[m["month"]] = running
    story.append(chart_image(create_area_chart(cumulative, ""), 17.2 * cm))

    doc.build(story)


def render_kpi_trend_dashboard_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_kpi_trend_dashboard(data, path)
    return _render_modern_kpi_trend_dashboard(data, path)
