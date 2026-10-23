"""Report: historical_growth."""

from firefly_reports.reports.historical_growth.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"historical_growth_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.historical_growth.pdf import render_historical_report_pdf

    render_historical_report_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return ctx.period.year_mode and not ctx.options.legacy


def _pdf_enabled(ctx: ReportContext, data: ReportData) -> bool:
    return bool(data)


SPEC = ReportSpec(
    key="historical_growth",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
    pdf_enabled=_pdf_enabled,
)
