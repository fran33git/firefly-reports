"""Report: yoy."""

from typing import Any

from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)
from firefly_reports.reports.yoy.build import from_source


def _filename(ctx: ReportContext) -> str:
    return f"yoy_{ctx.period.previous.start.year}_vs_{ctx.period.start.year}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.yoy.pdf import render_yoy_pdf

    render_yoy_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.yoy.xlsx import write_sheet

    write_sheet(wb, data)


def _applies(ctx: ReportContext) -> bool:
    return ctx.period.year_mode


SPEC = ReportSpec(
    key="yoy",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
    applies=_applies,
)
