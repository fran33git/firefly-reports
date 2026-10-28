"""Report: liabilities."""

from typing import Any

from firefly_reports.reports.liabilities.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"liabilities_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.liabilities.pdf import render_liabilities_pdf

    render_liabilities_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.liabilities.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="liabilities",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
