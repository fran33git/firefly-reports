"""Report: tagged."""

from typing import Any

from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)
from firefly_reports.reports.tagged.build import from_source


def _filename(ctx: ReportContext) -> str:
    return f"tagged_{'_'.join(ctx.options.tags)[:30]}_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.tagged.pdf import render_tagged_report_pdf

    render_tagged_report_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.tagged.xlsx import write_sheet

    write_sheet(wb, data)


def _pdf_enabled(ctx: ReportContext, data: ReportData) -> bool:
    return bool(ctx.options.tags)


SPEC = ReportSpec(
    key="tagged",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
    pdf_enabled=_pdf_enabled,
)
