"""The registry lists every report once, in the order the 1.x workbook used."""

from firefly_reports.reports.registry import REPORTS, get, keys

SHEET_ORDER = [
    "cash_flow",
    "income_expense",
    "transaction_register",
    "net_worth",
    "account_statements",
    "tax_summary",
    "expense_trend",
    "tagged",
    "budget_vs_actual",
    "bills",
    "savings_goals",
    "liabilities",
    "kpi_scorecard",
    "yoy",
    "cumulative_cashflow",
    "income_concentration",
    "summary",
]


def test_registry_has_26_reports_and_2_views():
    assert len([s for s in REPORTS if not s.view]) == 26
    assert {s.key for s in REPORTS if s.view} == {"dashboard_income_expense", "dashboard_kpi_trend"}


def test_registry_sheet_order_matches_1x():
    assert [s.key for s in REPORTS if s.sheet] == SHEET_ORDER


def test_registry_dependencies_precede():
    seen: set[str] = set()
    for spec in REPORTS:
        assert set(spec.depends_on) <= seen, spec.key
        seen.add(spec.key)


def test_registry_keys_are_unique_and_addressable():
    assert len(set(keys())) == len(REPORTS) == 28
    assert get("yoy").key == "yoy"
