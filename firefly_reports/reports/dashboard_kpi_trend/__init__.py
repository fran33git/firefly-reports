"""Report: dashboard_kpi_trend."""

from collections.abc import Mapping

from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
    SourceData,
)


def _filename(ctx: ReportContext) -> str:
    return f"dashboard_kpi_trend_{ctx.period.tag}.pdf"


def _build(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Derived view: no builder of its own."""
    return built["kpi_scorecard"]


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.dashboard_kpi_trend.pdf import render_kpi_trend_dashboard_pdf

    render_kpi_trend_dashboard_pdf(data, path, legacy=legacy)


SPEC = ReportSpec(
    key="dashboard_kpi_trend",
    build=_build,
    pdf=_pdf,
    filename=_filename,
    depends_on=("kpi_scorecard",),
    view=True,
)
