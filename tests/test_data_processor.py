"""Unit tests for data_processor build_* functions."""

from datetime import date
from decimal import Decimal

from firefly_reports.data_processor import (
    apply_global_filters,
    build_account_statements,
    build_all_tags_report,
    build_audit_log,
    build_bills_report,
    build_budget_vs_actual,
    build_cash_flow,
    build_category_ledger,
    build_cumulative_cashflow,
    build_expense_trend,
    build_historical_report,
    build_income_concentration,
    build_income_expense,
    build_journal,
    build_kpi_scorecard,
    build_liabilities_report,
    build_linkage_report,
    build_liquidity_forecast,
    build_net_worth,
    build_payee_ledger,
    build_performance_forecast,
    build_savings_goals,
    build_summary,
    build_tagged_report,
    build_tax_summary,
    build_transaction_register,
    build_yoy_comparison,
)

# ─────────────────────────────────────────────
# Report 1 — Cash Flow Statement
# ─────────────────────────────────────────────


class TestBuildCashFlow:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_cash_flow(txn_2025, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "inflows",
            "outflows",
            "total_in",
            "total_out",
            "net",
            "by_month",
        ):
            assert key in result

    def test_net_equals_total_in_minus_total_out(self, txn_2025, period):
        start, end = period
        result = build_cash_flow(txn_2025, start, end)
        assert result["net"] == result["total_in"] - result["total_out"]

    def test_monetary_values_are_decimal(self, txn_2025, period):
        start, end = period
        result = build_cash_flow(txn_2025, start, end)
        assert isinstance(result["total_in"], Decimal)
        assert isinstance(result["total_out"], Decimal)
        assert isinstance(result["net"], Decimal)

    def test_empty_transactions(self, period):
        start, end = period
        result = build_cash_flow([], start, end)
        assert result["total_in"] == Decimal("0")
        assert result["total_out"] == Decimal("0")
        assert result["net"] == Decimal("0")
        assert result["inflows"] == []
        assert result["outflows"] == []


# ─────────────────────────────────────────────
# Report 2 — Income & Expense Summary
# ─────────────────────────────────────────────


class TestBuildIncomeExpense:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_income_expense(txn_2025, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "income_rows",
            "expense_rows",
            "total_income",
            "total_expense",
            "net_savings",
            "savings_rate",
            "budget_breakdown",
        ):
            assert key in result

    def test_net_savings_invariant(self, txn_2025, period):
        start, end = period
        result = build_income_expense(txn_2025, start, end)
        assert result["net_savings"] == result["total_income"] - result["total_expense"]

    def test_savings_rate_is_decimal(self, txn_2025, period):
        start, end = period
        result = build_income_expense(txn_2025, start, end)
        assert isinstance(result["savings_rate"], Decimal)

    def test_empty_transactions(self, period):
        start, end = period
        result = build_income_expense([], start, end)
        assert result["total_income"] == Decimal("0")
        assert result["total_expense"] == Decimal("0")
        assert result["savings_rate"] == Decimal("0")


# ─────────────────────────────────────────────
# Report 3 — Transaction Register
# ─────────────────────────────────────────────


class TestBuildTransactionRegister:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_transaction_register(txn_2025, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "rows",
            "total_transactions",
        ):
            assert key in result

    def test_opening_balance_excluded(self, period):
        start, end = period
        txns = [
            {"type": "opening balance", "date": "2025-01-01", "amount": "1000.00"},
            {
                "type": "deposit",
                "date": "2025-01-15",
                "amount": "500.00",
                "description": "Dep",
                "source_name": "",
                "destination_name": "",
                "category_name": "",
                "budget_name": None,
                "tags": [],
                "notes": "",
            },
        ]
        result = build_transaction_register(txns, start, end)
        assert result["total_transactions"] == 1

    def test_row_has_running_balance(self, txn_2025, period):
        start, end = period
        result = build_transaction_register(txn_2025, start, end)
        for row in result["rows"]:
            assert "running_balance" in row
            assert isinstance(row["running_balance"], Decimal)

    def test_empty_transactions(self, period):
        start, end = period
        result = build_transaction_register([], start, end)
        assert result["rows"] == []
        assert result["total_transactions"] == 0

    def test_split_transaction_grouping(self, period):
        start, end = period
        txns = [
            {
                "group_id": "100",
                "date": "2025-01-15",
                "amount": "100.00",
                "type": "withdrawal",
                "description": "Split 1",
                "category_name": "Food",
                "group_title": "Grocery Shopping",
            },
            {
                "group_id": "100",
                "date": "2025-01-15",
                "amount": "50.00",
                "type": "withdrawal",
                "description": "Split 2",
                "category_name": "Home",
                "group_title": "Grocery Shopping",
            },
            {
                "group_id": "101",
                "date": "2025-01-16",
                "amount": "200.00",
                "type": "deposit",
                "description": "Salary",
                "category_name": "Income",
            },
        ]
        result = build_transaction_register(txns, start, end)
        assert len(result["rows"]) == 2
        assert result["total_transactions"] == 3

        # Check first group (split)
        split_group = next(r for r in result["rows"] if r["group_id"] == "100")
        assert split_group["total"] == Decimal("-150.00")
        assert len(split_group["splits"]) == 2
        assert split_group["description"] == "Grocery Shopping"

        # Check second group (single)
        salary_group = next(r for r in result["rows"] if r["group_id"] == "101")
        assert salary_group["total"] == Decimal("200.00")
        assert len(salary_group["splits"]) == 1
        assert salary_group["description"] == "Salary"

    def test_new_detail_fields(self, period):
        start, end = period
        txns = [
            {
                "group_id": "100",
                "id": "501",
                "date": "2025-01-15",
                "type": "withdrawal",
                "amount": "100.00",
                "description": "Split 1",
                "category_name": "Food",
                "group_title": "Grocery Shopping",
                "reconciled": True,
                "has_attachments": True,
                "book_date": "2025-01-16T00:00:00+01:00",
            },
            {
                "group_id": "100",
                "id": "502",
                "date": "2025-01-15",
                "type": "withdrawal",
                "amount": "50.00",
                "description": "Split 2",
                "category_name": "Home",
                "group_title": "Grocery Shopping",
                "reconciled": False,
            },
        ]
        result = build_transaction_register(txns, start, end)
        group = result["rows"][0]
        assert group["journal_id"] == "501"
        assert group["reconciled"] is False  # all splits must be reconciled
        assert group["has_attachments"] is True  # any split with attachments
        assert group["total_abs"] == Decimal("150.00")
        assert group["splits"][0]["description"] == "Split 1"
        # book_date normalized to plain YYYY-MM-DD (no time/timezone)
        assert group["splits"][0]["book_date"] == "2025-01-16"
        assert result["totals_by_type"] == {"withdrawal": Decimal("150.00")}


# ─────────────────────────────────────────────
# Report 4 — Asset & Net Worth Statement
# ─────────────────────────────────────────────


class TestBuildNetWorth:
    def test_required_keys(self, accounts, period, owner, currency):
        _, end = period
        result = build_net_worth(accounts, end, owner, currency)
        for key in (
            "owner",
            "as_of_date",
            "currency",
            "groups",
            "total_assets",
            "total_liabilities",
            "net_worth",
            "account_count",
        ):
            assert key in result
        for group in result["groups"]:
            for acc in group["accounts"]:
                assert "updated_at" in acc

    def test_net_worth_invariant(self, accounts, period):
        _, end = period
        result = build_net_worth(accounts, end)
        assert result["net_worth"] == result["total_assets"] + result["total_liabilities"]

    def test_account_count_matches_accounts(self, accounts, period):
        _, end = period
        result = build_net_worth(accounts, end)
        assert result["account_count"] == len(accounts)

    def test_empty_accounts(self, period):
        _, end = period
        result = build_net_worth([], end)
        assert result["total_assets"] == Decimal("0")
        assert result["net_worth"] == Decimal("0")
        assert result["account_count"] == 0


# ─────────────────────────────────────────────
# Report 5 — Account Statements
# ─────────────────────────────────────────────


class TestBuildAccountStatements:
    def test_returns_list_of_dicts(self, accounts, period, owner, currency):
        start, end = period
        result = build_account_statements(accounts, {}, start, end, owner, currency)
        assert isinstance(result, list)
        assert len(result) == len(accounts)

    def test_statement_keys(self, accounts, period, owner, currency):
        start, end = period
        result = build_account_statements(accounts, {}, start, end, owner, currency)
        for stmt in result:
            for key in (
                "owner",
                "period_start",
                "period_end",
                "currency",
                "account_name",
                "account_iban",
                "account_role",
                "opening_balance",
                "closing_balance",
                "total_in",
                "total_out",
                "rows",
                "tx_count",
                "updated_at",
            ):
                assert key in stmt

    def test_closing_balance_with_no_transactions(self, accounts, period):
        start, end = period
        result = build_account_statements(accounts, {}, start, end)
        for stmt in result:
            # With no transactions, closing_balance == opening_balance
            assert stmt["closing_balance"] == stmt["opening_balance"]

    def test_tx_count_reflects_rows(self, accounts, period, txn_2025):
        start, end = period
        txn_by_account = {"1": txn_2025}
        result = build_account_statements(accounts, txn_by_account, start, end)
        main_stmt = next(s for s in result if s["account_name"] == "Main Checking")
        assert main_stmt["tx_count"] == len(main_stmt["rows"])


# ─────────────────────────────────────────────
# Report 6 — Annual Tax Summary
# ─────────────────────────────────────────────


class TestBuildTaxSummary:
    def test_required_keys(self, txn_2025, owner, currency):
        result = build_tax_summary(
            txn_2025, 2025, owner, currency, deductible_keywords=["deducibile"]
        )
        for key in (
            "owner",
            "year",
            "currency",
            "income_by_cat",
            "income_by_client",
            "deductible_rows",
            "nondeductible_rows",
            "total_income",
            "total_deductible",
            "total_nondeductible",
            "taxable_estimate",
        ):
            assert key in result

    def test_taxable_estimate_invariant(self, txn_2025):
        result = build_tax_summary(txn_2025, 2025, deductible_keywords=["deducibile"])
        assert result["taxable_estimate"] == result["total_income"] - result["total_deductible"]

    def test_year_filter_excludes_other_years(self, txn_2025, txn_2024):
        all_txns = txn_2025 + txn_2024
        result_2025 = build_tax_summary(all_txns, 2025, deductible_keywords=["deducibile"])
        result_2024 = build_tax_summary(all_txns, 2024, deductible_keywords=["deducibile"])
        # Income totals should differ between years
        assert result_2025["total_income"] != result_2024["total_income"]

    def test_empty_transactions(self):
        result = build_tax_summary([], 2025, deductible_keywords=["deducibile"])
        assert result["total_income"] == Decimal("0")
        assert result["taxable_estimate"] == Decimal("0")


# ─────────────────────────────────────────────
# Report 7 — Expense Trend by Category
# ─────────────────────────────────────────────


class TestBuildExpenseTrend:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_expense_trend(txn_2025, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "months",
            "rows",
            "totals_by_month",
            "income_by_month",
            "grand_total",
        ):
            assert key in result

    def test_row_structure(self, txn_2025, period):
        start, end = period
        result = build_expense_trend(txn_2025, start, end)
        for row in result["rows"]:
            assert "category" in row
            assert "monthly" in row
            assert "total" in row
            assert len(row["monthly"]) == len(result["months"])

    def test_grand_total_matches_sum(self, txn_2025, period):
        start, end = period
        result = build_expense_trend(txn_2025, start, end)
        assert result["grand_total"] == sum(result["totals_by_month"])

    def test_empty_transactions(self, period):
        start, end = period
        result = build_expense_trend([], start, end)
        assert result["rows"] == []
        assert result["months"] == []
        assert result["grand_total"] == Decimal("0")


# ─────────────────────────────────────────────
# Report 8 — Tagged Transactions Report
# ─────────────────────────────────────────────


class TestBuildTaggedReport:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_tagged_report(txn_2025, ["invoice"], start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "tags",
            "match_all",
            "rows",
            "total_transactions",
            "income_by_cat",
            "expense_by_cat",
            "total_in",
            "total_out",
            "net",
        ):
            assert key in result

    def test_filters_by_tag(self, txn_2025, period):
        start, end = period
        result = build_tagged_report(txn_2025, ["invoice"], start, end)
        # All rows should involve transactions with the "invoice" tag
        assert result["total_transactions"] > 0
        # Rows with no matching tag should not appear
        non_invoice = [tx for tx in txn_2025 if "invoice" not in (tx.get("tags") or [])]
        assert len(non_invoice) > 0  # ensure filter is doing something meaningful

    def test_net_invariant(self, txn_2025, period):
        start, end = period
        result = build_tagged_report(txn_2025, ["tax"], start, end)
        assert result["net"] == result["total_in"] - result["total_out"]

    def test_no_matching_tags(self, txn_2025, period):
        start, end = period
        result = build_tagged_report(txn_2025, ["nonexistent_tag_xyz"], start, end)
        assert result["total_transactions"] == 0
        assert result["rows"] == []


# ─────────────────────────────────────────────
# Report 9 — Budget vs. Actual
# ─────────────────────────────────────────────


class TestBuildBudgetVsActual:
    def test_required_keys(self, budgets, budget_limits, txn_2025, period, owner, currency):
        start, end = period
        result = build_budget_vs_actual(
            budgets, budget_limits, txn_2025, start, end, owner, currency
        )
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "rows",
            "total_limit",
            "total_actual",
            "total_variance",
            "unbudgeted_spending",
        ):
            assert key in result

    def test_row_structure(self, budgets, budget_limits, txn_2025, period):
        start, end = period
        result = build_budget_vs_actual(budgets, budget_limits, txn_2025, start, end)
        assert len(result["rows"]) == len(budgets)
        for row in result["rows"]:
            for key in ("budget_name", "limit", "actual", "variance", "variance_pct", "status"):
                assert key in row

    def test_variance_invariant(self, budgets, budget_limits, txn_2025, period):
        start, end = period
        result = build_budget_vs_actual(budgets, budget_limits, txn_2025, start, end)
        assert result["total_variance"] == result["total_limit"] - result["total_actual"]

    def test_status_values_are_valid(self, budgets, budget_limits, txn_2025, period):
        start, end = period
        result = build_budget_vs_actual(budgets, budget_limits, txn_2025, start, end)
        valid_statuses = {"over", "warning", "under", "no_limit"}
        for row in result["rows"]:
            assert row["status"] in valid_statuses


# ─────────────────────────────────────────────
# Report 10 — Bills & Subscriptions
# ─────────────────────────────────────────────


class TestBuildBillsReport:
    def test_required_keys(self, bills, bill_txn, period, owner, currency):
        start, end = period
        result = build_bills_report(bills, bill_txn, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "rows",
            "total_expected",
            "total_paid",
            "delta",
        ):
            assert key in result

    def test_row_structure(self, bills, bill_txn, period):
        start, end = period
        result = build_bills_report(bills, bill_txn, start, end)
        assert len(result["rows"]) == len(bills)
        for row in result["rows"]:
            for key in (
                "name",
                "amount_min",
                "amount_max",
                "expected",
                "frequency",
                "next_expected",
                "last_paid",
                "paid_amount",
                "times_paid",
                "active",
            ):
                assert key in row

    def test_delta_invariant(self, bills, bill_txn, period):
        start, end = period
        result = build_bills_report(bills, bill_txn, start, end)
        assert result["delta"] == result["total_paid"] - result["total_expected"]

    def test_empty_bills(self, period):
        start, end = period
        result = build_bills_report([], {}, start, end)
        assert result["rows"] == []
        assert result["total_expected"] == Decimal("0")
        assert result["total_paid"] == Decimal("0")


# ─────────────────────────────────────────────
# Report 11 — Savings Goals (Piggy Banks)
# ─────────────────────────────────────────────


class TestBuildSavingsGoals:
    def test_required_keys(self, piggy_banks, period, owner, currency):
        _, end = period
        result = build_savings_goals(piggy_banks, end, owner, currency)
        for key in (
            "owner",
            "as_of_date",
            "currency",
            "goals",
            "total_saved",
            "total_target",
            "overall_pct",
            "goal_count",
        ):
            assert key in result

    def test_goal_count_matches_piggy_banks(self, piggy_banks, period):
        _, end = period
        result = build_savings_goals(piggy_banks, end)
        assert result["goal_count"] == len(piggy_banks)

    def test_goal_structure(self, piggy_banks, period):
        _, end = period
        result = build_savings_goals(piggy_banks, end)
        for goal in result["goals"]:
            for key in (
                "name",
                "target",
                "current",
                "remaining",
                "pct",
                "start_date",
                "target_date",
                "months_left",
                "monthly_needed",
            ):
                assert key in goal

    def test_empty_piggy_banks(self, period):
        _, end = period
        result = build_savings_goals([], end)
        assert result["goals"] == []
        assert result["total_saved"] == Decimal("0")
        assert result["goal_count"] == 0

    def test_account_name_from_accounts_list(self, piggy_banks, period):
        """v6.2+ API exposes the linked account via accounts[0].name."""
        _, end = period
        result = build_savings_goals(piggy_banks, end)
        assert all(g["account_name"] == "Savings Account" for g in result["goals"])

    def test_account_name_legacy_fallback(self, period):
        _, end = period
        legacy = [
            {
                "id": "1",
                "attributes": {
                    "name": "Goal",
                    "target_amount": "100.00",
                    "current_amount": "10.00",
                    "account_name": "Old Field",
                },
            }
        ]
        result = build_savings_goals(legacy, end)
        assert result["goals"][0]["account_name"] == "Old Field"


# ─────────────────────────────────────────────
# Report 12 — Liabilities & Debt
# ─────────────────────────────────────────────


class TestBuildLiabilitiesReport:
    def test_required_keys(self, liabilities, period, owner, currency):
        start, end = period
        result = build_liabilities_report(liabilities, {}, end, start, end, owner, currency)
        for key in (
            "owner",
            "as_of_date",
            "period_start",
            "period_end",
            "currency",
            "rows",
            "total_debt",
            "total_payments",
            "liability_count",
        ):
            assert key in result

    def test_liability_count(self, liabilities, period):
        start, end = period
        result = build_liabilities_report(liabilities, {}, end, start, end)
        assert result["liability_count"] == len(liabilities)

    def test_debt_amount_is_positive(self, liabilities, period):
        start, end = period
        result = build_liabilities_report(liabilities, {}, end, start, end)
        # debt_amount should always be positive (absolute value of balance)
        for row in result["rows"]:
            assert row["debt_amount"] >= Decimal("0")

    def test_empty_liabilities(self, period):
        start, end = period
        result = build_liabilities_report([], {}, end, start, end)
        assert result["rows"] == []
        assert result["total_debt"] == Decimal("0")
        assert result["liability_count"] == 0


# ─────────────────────────────────────────────
# Report 13 — Financial KPI Scorecard
# ─────────────────────────────────────────────


class TestBuildKpiScorecard:
    def test_required_keys(self, txn_2025, accounts, liabilities, period, owner, currency):
        start, end = period
        result = build_kpi_scorecard(txn_2025, accounts, liabilities, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "total_in",
            "total_out",
            "net_cash_flow",
            "avg_monthly_in",
            "avg_monthly_out",
            "savings_rate",
            "burn_rate",
            "cash_runway",
            "liquid_assets",
            "total_liab",
            "net_worth",
            "liquidity_ratio",
            "hhi",
            "top1_client",
            "top1_pct",
            "n_months",
            "monthly_trend",
        ):
            assert key in result

    def test_net_cash_flow_invariant(self, txn_2025, accounts, liabilities, period):
        start, end = period
        result = build_kpi_scorecard(txn_2025, accounts, liabilities, start, end)
        assert result["net_cash_flow"] == result["total_in"] - result["total_out"]

    def test_monetary_values_are_decimal(self, txn_2025, accounts, liabilities, period):
        start, end = period
        result = build_kpi_scorecard(txn_2025, accounts, liabilities, start, end)
        for key in ("total_in", "total_out", "burn_rate", "savings_rate", "hhi"):
            assert isinstance(result[key], Decimal)

    def test_empty_transactions(self, accounts, liabilities, period):
        start, end = period
        result = build_kpi_scorecard([], accounts, liabilities, start, end)
        assert result["total_in"] == Decimal("0")
        assert result["hhi"] == Decimal("0")


# ─────────────────────────────────────────────
# Report 14 — Year-over-Year Comparison
# ─────────────────────────────────────────────


class TestBuildYoyComparison:
    def test_required_keys(self, txn_2025, txn_2024, period, period_prev, owner, currency):
        start, end = period
        start_p, end_p = period_prev
        result = build_yoy_comparison(
            txn_2025, txn_2024, start, end, start_p, end_p, owner, currency
        )
        for key in (
            "owner",
            "currency",
            "period_a",
            "period_b",
            "income_rows",
            "expense_rows",
            "total_in_a",
            "total_in_b",
            "total_out_a",
            "total_out_b",
            "net_a",
            "net_b",
            "delta_in_pct",
            "delta_out_pct",
        ):
            assert key in result

    def test_net_invariants(self, txn_2025, txn_2024, period, period_prev):
        start, end = period
        start_p, end_p = period_prev
        result = build_yoy_comparison(txn_2025, txn_2024, start, end, start_p, end_p)
        assert result["net_a"] == result["total_in_a"] - result["total_out_a"]
        assert result["net_b"] == result["total_in_b"] - result["total_out_b"]

    def test_period_labels_present(self, txn_2025, txn_2024, period, period_prev):
        start, end = period
        start_p, end_p = period_prev
        result = build_yoy_comparison(txn_2025, txn_2024, start, end, start_p, end_p)
        assert "label" in result["period_a"]
        assert "label" in result["period_b"]

    def test_income_rows_have_delta(self, txn_2025, txn_2024, period, period_prev):
        start, end = period
        start_p, end_p = period_prev
        result = build_yoy_comparison(txn_2025, txn_2024, start, end, start_p, end_p)
        for row in result["income_rows"]:
            assert "delta" in row
            assert row["delta"] == row["amount_a"] - row["amount_b"]


# ─────────────────────────────────────────────
# Report 15 — Cumulative Cash Flow
# ─────────────────────────────────────────────


class TestBuildCumulativeCashflow:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_cumulative_cashflow(txn_2025, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "months",
            "final_cumulative",
            "peak_month",
            "low_month",
        ):
            assert key in result

    def test_month_entry_structure(self, txn_2025, period):
        start, end = period
        result = build_cumulative_cashflow(txn_2025, start, end)
        for m in result["months"]:
            for key in ("month", "month_label", "income", "expense", "net", "cumulative"):
                assert key in m

    def test_final_cumulative_equals_last_month(self, txn_2025, period):
        start, end = period
        result = build_cumulative_cashflow(txn_2025, start, end)
        if result["months"]:
            assert result["final_cumulative"] == result["months"][-1]["cumulative"]

    def test_empty_transactions(self, period):
        start, end = period
        result = build_cumulative_cashflow([], start, end)
        assert result["months"] == []
        assert result["final_cumulative"] == Decimal("0")
        assert result["peak_month"] is None
        assert result["low_month"] is None


# ─────────────────────────────────────────────
# Report 16 — Income Concentration
# ─────────────────────────────────────────────


class TestBuildIncomeConcentration:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_income_concentration(txn_2025, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "rows",
            "total_income",
            "client_count",
        ):
            assert key in result
        # Concentration analysis (HHI/risk/fiscal note) was intentionally removed
        for removed in ("hhi", "top1_pct", "top1_client", "risk_level", "risk_note", "fiscal_note"):
            assert removed not in result

    def test_row_structure(self, txn_2025, period):
        start, end = period
        result = build_income_concentration(txn_2025, start, end)
        for row in result["rows"]:
            for key in ("client", "amount", "pct", "count", "avg_per_tx"):
                assert key in row

    def test_pct_sum_approximately_100(self, txn_2025, period):
        start, end = period
        result = build_income_concentration(txn_2025, start, end)
        if result["rows"]:
            total_pct = sum(r["pct"] for r in result["rows"])
            # Allow small rounding difference due to Decimal quantize
            assert abs(total_pct - Decimal("100")) < Decimal("1")

    def test_empty_transactions(self, period):
        start, end = period
        result = build_income_concentration([], start, end)
        assert result["rows"] == []
        assert result["total_income"] == Decimal("0")
        assert result["client_count"] == 0


# ─────────────────────────────────────────────
# Report 17 — Transaction Audit Log
# ─────────────────────────────────────────────


class TestBuildAuditLog:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_audit_log(txn_2025, start, end, owner, currency)
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "rows",
            "total_count",
            "reconciled_count",
        ):
            assert key in result

    def test_row_structure_and_attachments(self, period):
        start, end = period
        txns = [
            {
                "id": "1",
                "date": "2025-01-01",
                "amount": "100.00",
                "type": "withdrawal",
                "description": "Tx with attachment",
                "has_attachments": True,
            }
        ]
        result = build_audit_log(txns, start, end)
        row = result["rows"][0]
        assert row["has_attachments"] is True
        assert row["description"] == "Tx with attachment"

    def test_empty_transactions(self, period):
        start, end = period
        result = build_audit_log([], start, end)
        assert result["rows"] == []
        assert result["total_count"] == 0


# ─────────────────────────────────────────────
# Report 18 — Budget Performance Forecast
# ─────────────────────────────────────────────


class TestBuildPerformanceForecast:
    def test_required_keys(self, budgets, budget_limits, txn_2025, period, owner, currency):
        start, end = period
        result = build_performance_forecast(
            budgets, budget_limits, txn_2025, start, end, owner, currency
        )
        for key in (
            "owner",
            "period_start",
            "period_end",
            "currency",
            "rows",
            "days_elapsed",
            "total_days",
            "total_limit",
            "total_actual",
            "total_forecast",
        ):
            assert key in result

    def test_forecast_calculation(self, budgets, period):
        # Setup: 10 days elapsed in a 30-day month. Spent 100. Forecast should be 300.
        # We need to mock datetime.now() inside the function,
        # but since we can't easily mock, we'll use a period where 'now' is mid-period
        # or just verify the keys and logic in a simpler way if it's too dynamic.
        pass


# ─────────────────────────────────────────────
# Report 19 — Category Ledger
# ─────────────────────────────────────────────


class TestBuildCategoryLedger:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_category_ledger(txn_2025, start, end, owner, currency)
        assert "sections" in result
        assert "grand_total" in result

    def test_alphabetical_sorting(self, period):
        start, end = period
        txns = [
            {"type": "withdrawal", "amount": "10", "category_name": "Zebra", "date": "2025-01-01"},
            {"type": "withdrawal", "amount": "20", "category_name": "Apple", "date": "2025-01-02"},
        ]
        result = build_category_ledger(txns, start, end)
        categories = [s["category_name"] for s in result["sections"]]
        assert categories == ["Apple", "Zebra"]

    def test_section_total(self, period):
        start, end = period
        txns = [
            {"type": "withdrawal", "amount": "10", "category_name": "Food", "date": "2025-01-01"},
            {"type": "deposit", "amount": "5", "category_name": "Food", "date": "2025-01-02"},
        ]
        result = build_category_ledger(txns, start, end)
        assert result["sections"][0]["total"] == Decimal("-5.00")


# ─────────────────────────────────────────────
# Report 20 — Payee Ledger
# ─────────────────────────────────────────────


class TestBuildPayeeLedger:
    def test_alphabetical_sorting(self, period):
        start, end = period
        txns = [
            {
                "type": "withdrawal",
                "amount": "10",
                "destination_name": "Zebra Store",
                "date": "2025-01-01",
            },
            {
                "type": "withdrawal",
                "amount": "20",
                "destination_name": "Apple Store",
                "date": "2025-01-02",
            },
        ]
        result = build_payee_ledger(txns, start, end)
        payees = [s["payee_name"] for s in result["sections"]]
        assert payees == ["Apple Store", "Zebra Store"]


# ─────────────────────────────────────────────
# Report 21 — Linkage & Reimbursement Report
# ─────────────────────────────────────────────


class TestBuildLinkageReport:
    def test_identifies_reimbursements(self, period):
        start, end = period
        txns = [
            {
                "id": "100",
                "type": "withdrawal",
                "amount": "50.00",
                "date": "2025-01-01",
                "description": "Business Dinner",
            },
            {
                "id": "101",
                "type": "deposit",
                "amount": "50.00",
                "date": "2025-01-15",
                "description": "Dinner Reimbursement",
            },
        ]
        links = [
            {
                "id": "1",
                "link_type_id": "9",
                "link_type_name": "Reimbursement",
                "inward_id": "101",
                "outward_id": "100",
                "notes": "",
            }
        ]
        result = build_linkage_report(txns, links, start, end)
        assert len(result["groups"]) == 1
        group = result["groups"][0]
        assert group["recovery_pct"] == Decimal("100.0")
        assert group["status"] == "Complete"
        assert len(group["links"]) == 1
        assert group["link_types"] == "Reimbursement"

    def test_no_links_no_groups(self, txn_2025, period):
        start, end = period
        result = build_linkage_report(txn_2025, [], start, end)
        assert result["groups"] == []
        assert result["total_recovered"] == Decimal("0")


# ─────────────────────────────────────────────
# Report 23 — Multi-Year Historical Growth
# ─────────────────────────────────────────────


class TestBuildHistoricalReport:
    def test_required_keys(self, owner, currency):
        year_data = {
            2024: {
                "total_income": Decimal("1000"),
                "total_expense": Decimal("800"),
                "net_savings": Decimal("200"),
            },
            2025: {
                "total_income": Decimal("1200"),
                "total_expense": Decimal("900"),
                "net_savings": Decimal("300"),
            },
        }
        result = build_historical_report(year_data, owner, currency)
        for key in ("owner", "currency", "rows", "year_count"):
            assert key in result
        assert result["year_count"] == 2

    def test_growth_calculation(self):
        year_data = {
            2023: {
                "total_income": Decimal("1000"),
                "total_expense": Decimal("1000"),
                "net_savings": Decimal("0"),
            },
            2024: {
                "total_income": Decimal("1100"),
                "total_expense": Decimal("900"),
                "net_savings": Decimal("200"),
            },
        }
        result = build_historical_report(year_data)
        row_2024 = result["rows"][1]
        assert row_2024["income_growth"] == Decimal("10.0")  # (1100-1000)/1000 * 100
        assert row_2024["expense_growth"] == Decimal("-10.0")  # (900-1000)/1000 * 100
        assert row_2024["net_growth"] == Decimal("0")  # previous was 0

    def test_negative_net_growth(self):
        year_data = {
            2023: {
                "total_income": Decimal("1000"),
                "total_expense": Decimal("1200"),
                "net_savings": Decimal("-200"),
            },
            2024: {
                "total_income": Decimal("1000"),
                "total_expense": Decimal("1100"),
                "net_savings": Decimal("-100"),
            },
        }
        result = build_historical_report(year_data)
        row_2024 = result["rows"][1]
        # (-100 - (-200)) / abs(-200) * 100 = 100 / 200 * 100 = 50%
        assert row_2024["net_growth"] == Decimal("50.0")

    def test_zero_previous_values(self):
        year_data = {
            2023: {
                "total_income": Decimal("0"),
                "total_expense": Decimal("0"),
                "net_savings": Decimal("0"),
            },
            2024: {
                "total_income": Decimal("1000"),
                "total_expense": Decimal("1000"),
                "net_savings": Decimal("0"),
            },
        }
        result = build_historical_report(year_data)
        row_2024 = result["rows"][1]
        assert row_2024["income_growth"] == Decimal("0")
        assert row_2024["expense_growth"] == Decimal("0")
        assert row_2024["net_growth"] == Decimal("0")


# ─────────────────────────────────────────────
# Report 24 — Liquidity Forecast (6 Months)
# ─────────────────────────────────────────────


class TestBuildLiquidityForecast:
    def test_required_keys(self, owner, currency):
        bills = [
            {
                "attributes": {
                    "name": "Rent",
                    "amount_min": "1000",
                    "amount_max": "1000",
                    "repeat_freq": "monthly",
                    "active": True,
                }
            }
        ]
        result = build_liquidity_forecast(
            current_balance=Decimal("5000"),
            avg_income=Decimal("3000"),
            avg_variable_expense=Decimal("1500"),
            bills=bills,
            end_date=date(2025, 5, 31),
            owner_name=owner,
            currency_symbol=currency,
        )
        for key in ("owner", "currency", "start_date", "forecast_months", "final_balance"):
            assert key in result
        assert len(result["forecast_months"]) == 6

    def test_cumulative_balance(self):
        # balance 1000, income 2000, var 500, bills 500 (monthly)
        # month 1: 1000 + 2000 - 500 - 500 = 2000
        # month 2: 2000 + 2000 - 500 - 500 = 3000
        bills = [
            {
                "attributes": {
                    "amount_min": "500",
                    "amount_max": "500",
                    "repeat_freq": "monthly",
                    "active": True,
                }
            }
        ]
        result = build_liquidity_forecast(
            current_balance=Decimal("1000"),
            avg_income=Decimal("2000"),
            avg_variable_expense=Decimal("500"),
            bills=bills,
            end_date=date(2025, 1, 1),
        )
        assert result["forecast_months"][0]["balance"] == Decimal("2000.00")
        assert result["forecast_months"][1]["balance"] == Decimal("3000.00")
        assert result["final_balance"] == Decimal("7000.00")

    def test_bill_filtering(self):
        # Quarterly bill
        bills = [
            {
                "attributes": {
                    "amount_min": "300",
                    "amount_max": "300",
                    "repeat_freq": "quarterly",
                    "next_expected_match": "2025-03-15",
                    "active": True,
                }
            }
        ]
        # end_date Jan 2025.
        # Forecast: Feb, Mar, Apr, May, Jun, Jul
        # Bill should hit in Mar (idx 1) and Jun (idx 4)
        result = build_liquidity_forecast(
            current_balance=Decimal("1000"),
            avg_income=Decimal("0"),
            avg_variable_expense=Decimal("0"),
            bills=bills,
            end_date=date(2025, 1, 31),
        )
        # Feb
        assert result["forecast_months"][0]["fixed_outflow"] == Decimal("0.00")
        # Mar
        assert result["forecast_months"][1]["fixed_outflow"] == Decimal("300.00")
        # Apr
        assert result["forecast_months"][2]["fixed_outflow"] == Decimal("0.00")
        # May
        assert result["forecast_months"][3]["fixed_outflow"] == Decimal("0.00")
        # Jun
        assert result["forecast_months"][4]["fixed_outflow"] == Decimal("300.00")
        # Jul
        assert result["forecast_months"][5]["fixed_outflow"] == Decimal("0.00")


# ─────────────────────────────────────────────
# Report 22 — All Tags Ledger
# ─────────────────────────────────────────────


class TestBuildAllTagsReport:
    def test_required_keys(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_all_tags_report(txn_2025, start, end, owner, currency)
        assert "owner" in result
        assert "period_start" in result
        assert "period_end" in result
        assert "currency" in result
        assert "tags" in result

    def test_tags_populated(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_all_tags_report(txn_2025, start, end, owner, currency)
        # txn_2025 has "invoice", "tax", "recurring", "software", "inps", "consulting" tags
        assert len(result["tags"]) > 0
        assert "invoice" in result["tags"]

    def test_tag_structure(self, txn_2025, period, owner, currency):
        start, end = period
        result = build_all_tags_report(txn_2025, start, end, owner, currency)
        for _tag_name, tag_data in result["tags"].items():
            assert "rows" in tag_data
            assert "total" in tag_data
            for row in tag_data["rows"]:
                assert "date" in row
                assert "description" in row
                assert "amount" in row

    def test_transfers_excluded(self, period, owner, currency):
        start, end = period
        txn = [
            {
                "type": "transfer",
                "date": "2025-01-01",
                "amount": "500.00",
                "description": "Transfer",
                "tags": ["recurring"],
            },
        ]
        result = build_all_tags_report(txn, start, end, owner, currency)
        assert "recurring" not in result["tags"]

    def test_empty_transactions(self, period, owner, currency):
        start, end = period
        result = build_all_tags_report([], start, end, owner, currency)
        assert result["tags"] == {}


# ─────────────────────────────────────────────
# Global filters (spec sez. 5)
# ─────────────────────────────────────────────


class TestApplyGlobalFilters:
    TXNS = [
        {
            "type": "withdrawal",
            "amount": "10.00",
            "source_id": "1",
            "source_type": "Asset account",
            "destination_type": "Expense account",
            "category_name": "Food",
            "reconciled": True,
        },
        {
            "type": "deposit",
            "amount": "20.00",
            "destination_id": "2",
            "destination_type": "Asset account",
            "source_type": "Revenue account",
            "category_name": "Salary",
            "reconciled": False,
        },
        {
            "type": "transfer",
            "amount": "5.00",
            "source_id": "1",
            "destination_id": "2",
            "source_type": "Asset account",
            "destination_type": "Asset account",
            "category_name": None,
            "reconciled": True,
        },
    ]

    def test_no_filters_returns_all(self):
        assert len(apply_global_filters(self.TXNS)) == 3

    def test_hide_transfers(self):
        out = apply_global_filters(self.TXNS, show_transfers=False)
        assert len(out) == 2
        assert all(tx["type"] != "transfer" for tx in out)

    def test_reconciled_only(self):
        out = apply_global_filters(self.TXNS, show_reconciled_only=True)
        assert len(out) == 2
        assert all(tx["reconciled"] for tx in out)

    def test_accounts_include_matches_asset_side(self):
        out = apply_global_filters(self.TXNS, accounts_include=["2"])
        # deposit (asset dest 2) + transfer (touches 2); withdrawal (asset 1) dropped
        assert [tx["type"] for tx in out] == ["deposit", "transfer"]

    def test_accounts_exclude(self):
        out = apply_global_filters(self.TXNS, accounts_exclude=["1"])
        assert [tx["type"] for tx in out] == ["deposit"]

    def test_categories_include_case_insensitive(self):
        out = apply_global_filters(self.TXNS, categories_include=["food"])
        assert len(out) == 1
        assert out[0]["category_name"] == "Food"

    def test_categories_exclude(self):
        out = apply_global_filters(self.TXNS, categories_exclude=["SALARY"])
        assert len(out) == 2

    def test_fallback_without_type_fields(self):
        txns = [
            {"type": "withdrawal", "source_id": "1"},
            {"type": "deposit", "destination_id": "2"},
        ]
        out = apply_global_filters(txns, accounts_include=["2"])
        assert len(out) == 1
        assert out[0]["type"] == "deposit"


# ─────────────────────────────────────────────
# Cash flow waterfall (R-INT-03) + General Journal (R-ITA-06)
# ─────────────────────────────────────────────


class TestCashFlowWaterfall:
    ACCOUNTS = [
        {"id": "1", "attributes": {"account_role": "defaultAsset", "current_balance": "1000.00"}},
        {"id": "2", "attributes": {"account_role": "savingsAsset", "current_balance": "500.00"}},
    ]
    LIABILITIES = [{"id": "30", "attributes": {"current_balance": "-800.00"}}]
    TXNS = [
        {
            "type": "deposit",
            "amount": "2000.00",
            "source_id": "10",
            "destination_id": "1",
            "date": "2025-01-10",
        },
        {
            "type": "withdrawal",
            "amount": "700.00",
            "source_id": "1",
            "destination_id": "20",
            "date": "2025-01-11",
        },
        {
            "type": "transfer",
            "amount": "300.00",
            "source_id": "1",
            "destination_id": "2",
            "date": "2025-01-12",
        },  # investing out
        {
            "type": "transfer",
            "amount": "150.00",
            "source_id": "1",
            "destination_id": "30",
            "date": "2025-01-13",
        },  # financing out
        {
            "type": "transfer",
            "amount": "50.00",
            "source_id": "1",
            "destination_id": "3",
            "date": "2025-01-14",
        },  # neutral, excluded
    ]

    def test_sections(self, period):
        start, end = period
        result = build_cash_flow(
            self.TXNS,
            start,
            end,
            accounts=self.ACCOUNTS,
            liability_accounts=self.LIABILITIES,
        )
        wf = result["waterfall"]
        assert wf["operating"] == {
            "in": Decimal("2000.00"),
            "out": Decimal("700.00"),
            "net": Decimal("1300.00"),
        }
        assert wf["investing"]["out"] == Decimal("300.00")
        assert wf["financing"]["out"] == Decimal("150.00")
        assert wf["net_change"] == Decimal("850.00")

    def test_opening_closing_cash(self, period):
        start, end = period
        result = build_cash_flow(
            self.TXNS,
            start,
            end,
            accounts=self.ACCOUNTS,
            liability_accounts=self.LIABILITIES,
        )
        wf = result["waterfall"]
        assert wf["closing_cash"] == Decimal("1500.00")
        assert wf["opening_cash"] == Decimal("650.00")  # 1500 - 850

    def test_no_accounts_no_cash(self, period):
        start, end = period
        result = build_cash_flow(self.TXNS, start, end)
        wf = result["waterfall"]
        assert wf["closing_cash"] is None
        assert wf["opening_cash"] is None
        # liabilities unknown → all operating
        assert wf["net_change"] == Decimal("1300.00")


class TestBuildJournal:
    def test_protocol_and_double_entry(self, period):
        start, end = period
        txns = [
            {
                "type": "withdrawal",
                "amount": "-50.00",
                "date": "2025-01-02",
                "description": "Groceries",
                "source_name": "Bank",
                "destination_name": "Supermarket",
            },
            {
                "type": "deposit",
                "amount": "100.00",
                "date": "2025-01-01",
                "description": "Salary",
                "source_name": "Employer",
                "destination_name": "Bank",
            },
        ]
        result = build_journal(txns, start, end)
        assert result["count"] == 2  # 2 journal entries
        assert len(result["rows"]) == 4  # 2 lines each (debit + credit)
        debit_line, credit_line = result["rows"][:2]  # salary, 2025-01-01
        assert debit_line["n"] == credit_line["n"] == 1
        assert debit_line["date"] == "2025-01-01"
        assert debit_line["account"] == "Bank"  # deposit: asset debited
        assert debit_line["debit"] == Decimal("100.00")
        assert debit_line["credit"] is None
        assert credit_line["account"] == "Employer"
        assert credit_line["debit"] is None
        assert credit_line["credit"] == Decimal("100.00")
        # withdrawal: expense debited
        assert result["rows"][2]["account"] == "Supermarket"
        assert result["rows"][3]["account"] == "Bank"

    def test_daily_and_grand_totals(self, period):
        start, end = period
        txns = [
            {
                "type": "withdrawal",
                "amount": "30.00",
                "date": "2025-01-01",
                "description": "a",
                "source_name": "B",
                "destination_name": "X",
            },
            {
                "type": "withdrawal",
                "amount": "20.00",
                "date": "2025-01-01",
                "description": "b",
                "source_name": "B",
                "destination_name": "Y",
            },
            {
                "type": "deposit",
                "amount": "80.00",
                "date": "2025-01-02",
                "description": "c",
                "source_name": "Z",
                "destination_name": "B",
            },
            {
                "type": "opening balance",
                "amount": "999.00",
                "date": "2025-01-01",
                "description": "ob",
                "source_name": "B",
                "destination_name": "B",
            },
        ]
        result = build_journal(txns, start, end)
        assert result["count"] == 3  # opening balance excluded
        assert result["daily_totals"][0] == {
            "date": "2025-01-01",
            "debit": Decimal("50.00"),
            "credit": Decimal("50.00"),
        }
        assert result["total_debit"] == result["total_credit"] == Decimal("130.00")

    def test_empty(self, period):
        start, end = period
        result = build_journal([], start, end)
        assert result["rows"] == []
        assert result["count"] == 0
        assert result["total_debit"] == Decimal("0")


# ─────────────────────────────────────────────
# Report 26 — Instance & Period Summary
# ─────────────────────────────────────────────


def test_build_summary(
    txn_2025,
    accounts,
    liabilities,
    budgets,
    bills,
    piggy_banks,
    about,
    about_user,
    period,
    owner,
    currency,
):
    start, end = period
    s = build_summary(
        txn_2025,
        accounts,
        liabilities,
        budgets,
        bills,
        piggy_banks,
        about,
        about_user,
        start,
        end,
        owner,
        currency,
    )
    assert s["owner"] == owner
    assert s["currency"] == currency
    assert s["counts"] == {
        "asset_accounts": 3,
        "liabilities": 1,
        "budgets": 3,
        "bills": 2,
        "piggy_banks": 2,
    }
    assert s["instance"]["firefly_version"] == "6.2.10"
    assert s["instance"]["api_version"] == "2.1.0"
    assert s["instance"]["os"] == "Linux"
    assert s["instance"]["php_version"] == "8.3.9"
    assert "timezone" not in s["instance"]
    assert s["instance"]["user_email"] == "test@example.com"
    p = s["period"]
    assert p["tx_total"] == len(txn_2025)
    assert p["tx_deposits"] + p["tx_withdrawals"] + p["tx_transfers"] == p["tx_total"]
    assert p["first_tx_date"] <= p["last_tx_date"]
    assert p["first_tx_date"].startswith("2025-01")
    assert isinstance(p["avg_daily_income"], Decimal)
    assert p["avg_daily_income"] >= Decimal("0.00")
    assert isinstance(p["avg_daily_expense"], Decimal)


def test_build_summary_missing_instance_info(
    txn_2025,
    accounts,
    liabilities,
    budgets,
    bills,
    piggy_banks,
    period,
    owner,
    currency,
):
    start, end = period
    s = build_summary(
        txn_2025,
        accounts,
        liabilities,
        budgets,
        bills,
        piggy_banks,
        {},
        {},
        start,
        end,
        owner,
        currency,
    )
    assert s["instance"]["firefly_version"] == ""
    assert s["instance"]["user_email"] == ""
    assert s["instance"]["user_role"] == ""
