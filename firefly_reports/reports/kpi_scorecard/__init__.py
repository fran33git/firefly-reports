"""Report: kpi_scorecard."""

from typing import Any

from firefly_reports.reports.kpi_scorecard.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"kpi_scorecard_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.kpi_scorecard.pdf import render_kpi_scorecard_pdf

    render_kpi_scorecard_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.kpi_scorecard.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="kpi_scorecard",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
