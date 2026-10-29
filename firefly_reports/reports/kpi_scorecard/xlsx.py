"""Excel sheet of the kpi_scorecard report."""

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import period_str
from firefly_reports.render.xlsx.layout import (
    data_row,
    header_row,
    title_block,
    to_number,
)
from firefly_reports.render.xlsx.styles import (
    LIGHT_HEX,
    thin,
)

# ─────────────────────────────────────────────────
# Monochrome palette
# ─────────────────────────────────────────────────


# ─────────────────────────────────────────────────
# Sheet 1 — Cash Flow Statement
# ─────────────────────────────────────────────────


def write_sheet(wb: Workbook, data: dict[str, Any]) -> None:
    ws = wb.create_sheet(t("excel.sheet_kpi"))
    period = period_str(data["period_start"], data["period_end"])
    row = title_block(ws, t("titles.kpi_scorecard"), data["owner"], period)
    sym = data["currency"]

    row = header_row(
        ws,
        row,
        [t("excel.kpi_indicator"), t("excel.kpi_value"), t("common.note")],
        col_widths=[36, 20, 40],
    )

    kpis = [
        (t("excel.kpi_savings_rate"), f"{data['savings_rate']} %", t("excel.kpi_savings_note")),
        (t("pdf.kpi_burn_rate"), to_number(data["burn_rate"]), t("pdf.kpi_burn_rate_note")),
        (
            t("excel.kpi_runway"),
            f"{data['cash_runway']} {t('pdf.kpi_runway_unit')}",
            t("excel.kpi_runway_note"),
        ),
        (t("pdf.kpi_net_worth"), to_number(data["net_worth"]), t("pdf.kpi_net_worth_note")),
        (
            t("excel.kpi_liquidity"),
            f"{data['liquidity_ratio']:.2f}x" if data["liquidity_ratio"] else "N/D",
            "Liquid Assets / Total Liabilities",
        ),
        (
            t("pdf.kpi_net_cash_flow"),
            to_number(data["net_cash_flow"]),
            t("pdf.kpi_net_cash_flow_note"),
        ),
        (
            t("pdf.kpi_avg_monthly_in"),
            to_number(data["avg_monthly_in"]),
            t("pdf.kpi_months_note").format(n_months=data["n_months"]),
        ),
        (
            t("pdf.kpi_avg_monthly_out"),
            to_number(data["avg_monthly_out"]),
            t("pdf.kpi_months_note").format(n_months=data["n_months"]),
        ),
        (t("pdf.kpi_hhi"), float(data["hhi"]), t("pdf.kpi_hhi_note")),
        (
            t("pdf.kpi_top_client"),
            f"{data['top1_client']} ({data['top1_pct']} %)",
            t("pdf.kpi_top_client_note"),
        ),
    ]
    for label, val, note in kpis:
        for col_idx, v in enumerate([label, val, note], start=1):
            c = ws.cell(row=row, column=col_idx, value=v)
            c.font = Font(name="Calibri", size=10)
            c.alignment = Alignment(
                horizontal="left" if col_idx != 2 else "right", vertical="center"
            )
            if col_idx == 2 and isinstance(v, float):
                c.number_format = "#,##0.00"
            c.border = Border(bottom=thin("EEEEEE"))
        ws.row_dimensions[row].height = 18
        row += 1

    row += 1
    ws.cell(row=row, column=1, value=t("pdf.trend_monthly")).font = Font(
        name="Calibri", bold=True, size=9, color=LIGHT_HEX
    )
    ws.row_dimensions[row].height = 20
    row += 1

    months_abbr = i18n.current().section("months_abbr")

    row = header_row(
        ws,
        row,
        [
            t("common.month"),
            f"{t('common.income')} ({sym})",
            f"{t('common.expense')} ({sym})",
            f"{t('common.net')} ({sym})",
            t("common.variation") + " %",
        ],
    )
    prev_net = None
    for m in data["monthly_trend"]:
        y, mo = m["month"].split("-")
        var_pct = None
        if prev_net and prev_net != 0:
            var_pct = float((m["net"] - prev_net) / abs(prev_net) * 100)
        prev_net = m["net"]
        row = data_row(
            ws,
            row,
            [
                f"{months_abbr.get(mo, mo)} {y}",
                to_number(m["income"]),
                to_number(m["expense"]),
                to_number(m["net"]),
                var_pct,
            ],
        )
        if var_pct is not None:
            ws.cell(row=row - 1, column=5).number_format = "0.0%"

    ws.freeze_panes = "A6"
    ws.sheet_view.showGridLines = False
