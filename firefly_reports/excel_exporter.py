"""Deprecated internal shim: the sheets live in ``firefly_reports.reports.<key>.xlsx``.

Removed before 2.0.0 ships.
"""

from pathlib import Path
from typing import Any

from firefly_reports.reports.account_statements.xlsx import write_sheet as _account_statements_sheet
from firefly_reports.reports.bills.xlsx import write_sheet as _bills_sheet
from firefly_reports.reports.budget_vs_actual.xlsx import write_sheet as _budget_vs_actual_sheet
from firefly_reports.reports.cash_flow.xlsx import write_sheet as _cash_flow_sheet
from firefly_reports.reports.cumulative_cashflow.xlsx import (
    write_sheet as _cumulative_cashflow_sheet,
)
from firefly_reports.reports.expense_trend.xlsx import write_sheet as _expense_trend_sheet
from firefly_reports.reports.income_concentration.xlsx import (
    write_sheet as _income_concentration_sheet,
)
from firefly_reports.reports.income_expense.xlsx import write_sheet as _income_expense_sheet
from firefly_reports.reports.kpi_scorecard.xlsx import write_sheet as _kpi_scorecard_sheet
from firefly_reports.reports.liabilities.xlsx import write_sheet as _liabilities_sheet
from firefly_reports.reports.net_worth.xlsx import write_sheet as _net_worth_sheet
from firefly_reports.reports.savings_goals.xlsx import write_sheet as _savings_goals_sheet
from firefly_reports.reports.summary.xlsx import write_sheet as _summary_sheet
from firefly_reports.reports.tagged.xlsx import write_sheet as _tagged_sheet
from firefly_reports.reports.tax_summary.xlsx import write_sheet as _tax_summary_sheet
from firefly_reports.reports.transaction_register.xlsx import (
    write_sheet as _transaction_register_sheet,
)
from firefly_reports.reports.workbook import write_workbook
from firefly_reports.reports.yoy.xlsx import write_sheet as _yoy_sheet

_SHEETS = (
    ("cf", _cash_flow_sheet),
    ("ie", _income_expense_sheet),
    ("reg", _transaction_register_sheet),
    ("net_worth", _net_worth_sheet),
    ("statements", _account_statements_sheet),
    ("tax", _tax_summary_sheet),
    ("trend", _expense_trend_sheet),
    ("tagged", _tagged_sheet),
    ("budget", _budget_vs_actual_sheet),
    ("bills", _bills_sheet),
    ("savings", _savings_goals_sheet),
    ("liabilities", _liabilities_sheet),
    ("kpi", _kpi_scorecard_sheet),
    ("yoy", _yoy_sheet),
    ("cumulative_cf", _cumulative_cashflow_sheet),
    ("concentration", _income_concentration_sheet),
    ("summary", _summary_sheet),
)


def render_all_xlsx_full(reports: dict[str, Any], output_path: str) -> None:
    """Write a workbook covering the core report types.

    Expected keys in reports: cf, ie, reg, net_worth, statements, tax, trend,
    tagged, budget, bills, savings, liabilities, kpi, yoy, cumulative_cf,
    concentration, summary. Sheets whose value is None or missing are skipped (e.g.
    yoy is unavailable in date-range mode).
    """
    write_workbook([(writer, reports.get(key)) for key, writer in _SHEETS], Path(output_path))
