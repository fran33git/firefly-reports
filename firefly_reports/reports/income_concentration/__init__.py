"""Report: income_concentration."""

from typing import Any

from firefly_reports.reports.income_concentration.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"income_concentration_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.income_concentration.pdf import render_income_concentration_pdf

    render_income_concentration_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.income_concentration.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="income_concentration",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
