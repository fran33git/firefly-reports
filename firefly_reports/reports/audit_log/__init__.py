"""Report: audit_log."""

from firefly_reports.reports.audit_log.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"audit_log_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.audit_log.pdf import render_audit_log_pdf

    render_audit_log_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return ctx.options.legacy


SPEC = ReportSpec(
    key="audit_log",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
)
