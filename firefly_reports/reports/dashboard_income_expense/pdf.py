"""PDF renderers of the dashboard_income_expense report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
)

from firefly_reports.i18n import t
from firefly_reports.render.charts import (
    create_bar_chart,
    create_cashflow_combo,
    create_donut_chart,
    create_horizontal_bar_chart,
    create_pie_chart,
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


def _render_legacy_income_expense_dashboard(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    fn = page_decorator(data["owner"], t("titles.dashboard_income_expense"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
        t("titles.dashboard_income_expense"), data["owner"], period, t("charts.spending_by_cat"), st
    )

    # Process data for charts
    # Spending by category (top 8)
    exp_rows = data.get("expense_rows") or data.get("expense_by_cat") or []
    exp_data = {r["category"]: float(r["amount"]) for r in exp_rows[:8]}
    if len(exp_rows) > 8:
        others_sum = sum(float(r["amount"]) for r in exp_rows[8:])
        exp_data[t("charts.others")] = others_sum

    pie_buf = create_pie_chart(exp_data, t("charts.spending_by_cat"))

    comp_data = {
        t("charts.income"): float(data["total_income"]),
        t("charts.expense"): float(data["total_expense"]),
    }
    bar_buf = create_bar_chart(comp_data, t("charts.income_vs_expense"))

    row1 = [
        [
            Image(pie_buf, width=8.5 * cm, height=6.5 * cm),
            Image(bar_buf, width=8.5 * cm, height=6.5 * cm),
        ]
    ]
    story.append(Table(row1, colWidths=[9 * cm, 9 * cm]))

    # Top 5 income sources
    income_srcs = data.get("income_by_client") or data.get("income_rows") or []
    src_data = {(r.get("client") or r.get("category")): float(r["amount"]) for r in income_srcs[:5]}
    top5_buf = create_horizontal_bar_chart(src_data, t("charts.top_income_sources"))
    story.append(Spacer(1, 1 * cm))
    story.append(Image(top5_buf, width=17 * cm, height=7 * cm))

    doc.build(story)


def _render_modern_income_expense_dashboard(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.dashboard_income_expense"), period)
    doc = make_doc(output_path, fn)
    story: list = []

    story += title_block(t("titles.dashboard_income_expense"), data["owner"], period, None, st)

    net = data["net_savings"]
    story.append(
        kpi_strip(
            [
                (
                    t("charts.total_income"),
                    fmt_num(data["total_income"], sym=sym, show_sym=True),
                    C_INCOME,
                ),
                (
                    t("charts.total_expense"),
                    fmt_num(data["total_expense"], sym=sym, show_sym=True),
                    C_EXPENSE,
                ),
                (
                    t("charts.net_savings"),
                    fmt_num(net, sym=sym, show_sym=True),
                    C_INCOME if net >= 0 else C_EXPENSE,
                ),
                (t("charts.savings_rate_card"), f"{data['savings_rate']}%", C_INK),
            ]
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    trend = data.get("monthly_trend") or []
    if trend:
        story.append(Paragraph(t("charts.monthly_income_expense").upper(), st["section"]))
        story.append(chart_image(create_cashflow_combo(trend, ""), 17.2 * cm))
        story.append(Spacer(1, 0.2 * cm))

    exp_rows = data.get("expense_rows") or data.get("expense_by_cat") or []
    exp_data = {r["category"]: float(r["amount"]) for r in exp_rows}
    income_srcs = data.get("income_by_client") or data.get("income_rows") or []
    src_data = {(r.get("client") or r.get("category")): float(r["amount"]) for r in income_srcs[:5]}

    story.append(
        KeepTogether(
            [
                Paragraph(t("charts.spending_by_cat").upper(), st["section"]),
                chart_image(create_donut_chart(exp_data, ""), 17.2 * cm),
            ]
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        KeepTogether(
            [
                Paragraph(t("charts.top_income_sources").upper(), st["section"]),
                chart_image(create_horizontal_bar_chart(src_data, ""), 17.2 * cm),
            ]
        )
    )

    doc.build(story)


def render_income_expense_dashboard_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_income_expense_dashboard(data, path)
    return _render_modern_income_expense_dashboard(data, path)
