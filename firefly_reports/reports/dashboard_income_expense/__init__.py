"""Report: dashboard_income_expense."""

from collections.abc import Mapping

from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
    SourceData,
)


def _filename(ctx: ReportContext) -> str:
    return f"dashboard_income_expense_{ctx.period.tag}.pdf"


def _build(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Derived view: no builder of its own."""
    return {**built["income_expense"], "monthly_trend": built["kpi_scorecard"]["monthly_trend"]}


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.dashboard_income_expense.pdf import (
        render_income_expense_dashboard_pdf,
    )

    render_income_expense_dashboard_pdf(data, path, legacy=legacy)


SPEC = ReportSpec(
    key="dashboard_income_expense",
    build=_build,
    pdf=_pdf,
    filename=_filename,
    depends_on=(
        "income_expense",
        "kpi_scorecard",
    ),
    view=True,
)
