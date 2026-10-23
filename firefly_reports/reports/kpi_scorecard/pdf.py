"""PDF renderers of the kpi_scorecard report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_kpi_scorecard(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.kpi_scorecard"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(t("titles.kpi_scorecard"), data["owner"], period, t("pdf.section_kpi"), st)

    # ── Section 1: Key KPIs in a two-column table
    def _kpi_row(label, value, note=""):
        return [
            Paragraph(label, st["cell_l"]),
            Paragraph(value, st["cell_r"]),
            Paragraph(note, st["small"]),
        ]

    CW_kpi = [7.0 * cm, 4.0 * cm, 6.9 * cm]

    liquidity_str = (
        f"{data['liquidity_ratio']:.2f}x" if data["liquidity_ratio"] is not None else "N/D"
    )

    kpi_rows = [
        [
            Paragraph(t("excel.kpi_indicator"), st["col_header_l"]),
            Paragraph(t("excel.kpi_value"), st["col_header"]),
            Paragraph(t("common.note"), st["col_header_l"]),
        ],
        _kpi_row(
            t("pdf.kpi_savings_rate"), f"{data['savings_rate']} %", t("pdf.kpi_savings_rate_note")
        ),
        _kpi_row(
            t("pdf.kpi_burn_rate"),
            fmt_num(data["burn_rate"], show_sym=True, sym=sym),
            t("pdf.kpi_burn_rate_note"),
        ),
        _kpi_row(
            t("pdf.kpi_runway"),
            f"{data['cash_runway']} {t('pdf.kpi_runway_unit')}",
            t("pdf.kpi_runway_note"),
        ),
        _kpi_row(
            t("pdf.kpi_net_worth"),
            fmt_num(data["net_worth"], show_sym=True, sym=sym, parens_neg=True),
            t("pdf.kpi_net_worth_note"),
        ),
        _kpi_row(t("pdf.kpi_liquidity"), liquidity_str, "Liquid Assets / Total Liabilities"),
        _kpi_row(
            t("pdf.kpi_net_cash_flow"),
            fmt_num(data["net_cash_flow"], show_sym=True, sym=sym, parens_neg=True),
            t("pdf.kpi_net_cash_flow_note"),
        ),
        _kpi_row(
            t("pdf.kpi_avg_monthly_in"),
            fmt_num(data["avg_monthly_in"], show_sym=True, sym=sym),
            t("pdf.kpi_months_note").format(n_months=data["n_months"]),
        ),
        _kpi_row(
            t("pdf.kpi_avg_monthly_out"),
            fmt_num(data["avg_monthly_out"], show_sym=True, sym=sym),
            t("pdf.kpi_months_note").format(n_months=data["n_months"]),
        ),
        _kpi_row(t("pdf.kpi_hhi"), f"{data['hhi']:.0f} / 10.000", t("pdf.kpi_hhi_note")),
        _kpi_row(
            t("pdf.kpi_top_client"),
            f"{data['top1_client']} ({data['top1_pct']} %)",
            t("pdf.kpi_top_client_note"),
        ),
    ]

    tbl = accounting_table(kpi_rows, CW_kpi, total_rows=[])
    story.append(tbl)

    # ── Section 2: Monthly trend
    if data["monthly_trend"]:
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph(t("pdf.trend_monthly"), st["section"]))

        months_abbr = i18n.current().section("months_abbr")
        CW_t = [3.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm, 3.9 * cm]
        trend_hdr = [
            [
                Paragraph(t("common.month"), st["col_header_l"]),
                Paragraph(t("common.income"), st["col_header"]),
                Paragraph(t("common.expense"), st["col_header"]),
                Paragraph(t("common.net"), st["col_header"]),
                Paragraph(t("common.variation"), st["col_header"]),
            ]
        ]
        trend_rows = list(trend_hdr)
        prev_net = None
        for m in data["monthly_trend"]:
            y, mo = m["month"].split("-")
            label = f"{months_abbr.get(mo, mo)} {y}"
            if prev_net is not None and prev_net != 0:
                var_pct = (m["net"] - prev_net) / abs(prev_net) * 100
                var_str = f"{var_pct:.1f} %"
            else:
                var_str = "—"
            prev_net = m["net"]
            trend_rows.append(
                [
                    Paragraph(label, st["cell_l"]),
                    Paragraph(fmt_num(m["income"]), st["cell_r"]),
                    Paragraph(fmt_num(m["expense"]), st["cell_r"]),
                    Paragraph(fmt_num(m["net"], parens_neg=True), st["cell_r"]),
                    Paragraph(var_str, st["cell_r"]),
                ]
            )
        story.append(accounting_table(trend_rows, CW_t))

    doc.build(story)


def render_kpi_scorecard_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_kpi_scorecard(data, path)
    return _render_legacy_kpi_scorecard(data, path)  # TODO: Modern
