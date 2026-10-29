"""Report: journal."""

from firefly_reports.reports.journal.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"journal_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.journal.pdf import render_journal_pdf

    render_journal_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return not ctx.options.legacy


SPEC = ReportSpec(
    key="journal",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
)
