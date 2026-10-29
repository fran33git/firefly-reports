"""Report: tax_summary."""

from typing import Any

from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)
from firefly_reports.reports.tax_summary.build import from_source


def _filename(ctx: ReportContext) -> str:
    return f"tax_summary_{ctx.period.start.year}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.tax_summary.pdf import render_tax_summary_pdf

    render_tax_summary_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.tax_summary.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="tax_summary",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
