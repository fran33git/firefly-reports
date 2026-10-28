"""Report: budget_forecast."""

from firefly_reports.reports.budget_forecast.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"budget_forecast_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.budget_forecast.pdf import render_forecast_pdf

    render_forecast_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return not ctx.options.legacy


SPEC = ReportSpec(
    key="budget_forecast",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
)
