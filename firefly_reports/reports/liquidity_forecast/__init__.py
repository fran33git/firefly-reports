"""Report: liquidity_forecast."""

from firefly_reports.reports.liquidity_forecast.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"liquidity_forecast_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.liquidity_forecast.pdf import render_liquidity_forecast_pdf

    render_liquidity_forecast_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return ctx.period.year_mode and not ctx.options.legacy


def _pdf_enabled(ctx: ReportContext, data: ReportData) -> bool:
    return bool(data)


SPEC = ReportSpec(
    key="liquidity_forecast",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
    pdf_enabled=_pdf_enabled,
    depends_on=("kpi_scorecard",),
)
