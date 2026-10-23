"""Report: summary."""

from typing import Any

from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)
from firefly_reports.reports.summary.build import from_source


def _filename(ctx: ReportContext) -> str:
    return f"summary_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.summary.pdf import render_summary_pdf

    render_summary_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.summary.xlsx import write_sheet

    write_sheet(wb, data)


def _pdf_enabled(ctx: ReportContext, data: ReportData) -> bool:
    return not ctx.options.legacy


SPEC = ReportSpec(
    key="summary",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
    pdf_enabled=_pdf_enabled,
)
