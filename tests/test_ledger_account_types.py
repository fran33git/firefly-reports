"""Account types the main fixture does not cover, end to end (offline).

``firefly_account_types.json`` holds one transaction per Firefly account type or shape that
``firefly_transactions.json`` lacks: mortgage/loan opening balances, the liability credit
account, import and cash accounts, default/beneficiary accounts, a reconciliation, foreign
amounts in both directions and an unnamed counterpart.
"""

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from firefly_reports.firefly_client import FireflyClient
from firefly_reports.ledger.export import build_from_splits, run_export
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import parse_ledger_config
from tests.ledger_helpers import export_request

FIXTURE = Path(__file__).parent / "fixtures" / "firefly_account_types.json"
needs_bean_check = pytest.mark.skipif(
    shutil.which("bean-check") is None, reason="bean-check not installed"
)


class RecordingClient:
    def __init__(self, splits):
        self.splits = splits
        self.calls = []

    def get_transactions(self, start=None, end=None, tx_type=None):
        self.calls.append(tx_type)
        return self.splits

    def get_transaction_links(self, resolve_types=True):
        return []


@pytest.fixture
def splits():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return FireflyClient._flatten_transactions(None, payload["data"])  # type: ignore[arg-type]


@pytest.fixture
def labels():
    return LedgerLabels.from_i18n()


@pytest.fixture
def ledger(splits, labels):
    config = parse_ledger_config({"classify_by": "account"})  # pins the counterpart naming
    return build_from_splits(splits, config, labels)


def accounts(ledger, jid):
    tx = next(t for t in ledger.transactions if t.firefly_id == jid)
    return {p.account: p for p in tx.postings}


def test_every_transaction_balances_per_currency(ledger):
    assert len(ledger.transactions) == 10
    for tx in ledger.transactions:
        assert all(v == 0 for v in tx.balance().values()), tx.firefly_id


def test_owed_mortgage_opening_balance_is_a_negative_liability(ledger):
    posts = accounts(ledger, "101")
    assert set(posts) == {"Equity:Opening-Balances", "Liabilities:Home-Mortgage"}
    assert posts["Liabilities:Home-Mortgage"].amount.number == Decimal("-120000.00")


def test_liability_credit_account_is_an_opening_balance_not_income(ledger):
    assert set(accounts(ledger, "102")) == {"Equity:Opening-Balances", "Liabilities:Friend-Loan"}


def test_transfer_to_a_mortgage_is_a_liability_posting(ledger):
    assert set(accounts(ledger, "103")) == {"Assets:Checking-Account", "Liabilities:Home-Mortgage"}


def test_import_account_is_a_technical_equity_counterpart(ledger):
    assert set(accounts(ledger, "104")) == {"Assets:Checking-Account", "Equity:Imports"}


def test_cash_account_maps_to_assets_cash(ledger):
    assert set(accounts(ledger, "105")) == {"Assets:Cash", "Assets:Checking-Account"}


def test_reconciliation_account_maps_to_equity(ledger):
    assert set(accounts(ledger, "106")) == {"Assets:Checking-Account", "Equity:Reconciliation"}


def test_default_and_beneficiary_accounts(ledger):
    assert set(accounts(ledger, "107")) == {"Assets:Checking-Account", "Expenses:Sports-Bar"}


def test_foreign_amount_on_a_deposit_prices_the_revenue_posting(ledger):
    revenue = accounts(ledger, "108")["Income:US-Client"]
    assert (revenue.amount.number, revenue.amount.currency) == (Decimal("-100.00"), "USD")
    assert revenue.price_total is not None
    assert (revenue.price_total.number, revenue.price_total.currency) == (Decimal("92.00"), "EUR")


def test_foreign_amount_on_a_withdrawal_prices_the_expense_posting(ledger):
    expense = accounts(ledger, "109")["Expenses:Hotel-Miami"]
    assert (expense.amount.number, expense.amount.currency) == (Decimal("50.00"), "USD")
    assert expense.price_total is not None
    assert (expense.price_total.number, expense.price_total.currency) == (Decimal("46.00"), "EUR")


def test_unnamed_counterpart_uses_the_fallback_account(ledger):
    assert "Expenses:Uncategorized" in accounts(ledger, "110")


def test_income_only_from_a_revenue_account(ledger):
    income = {
        a
        for tx in ledger.transactions
        for p in tx.postings
        if (a := p.account).startswith("Income")
    }
    assert income == {"Income:US-Client"}


def test_export_requests_every_transaction_type(splits, labels, tmp_path):
    client = RecordingClient(splits)
    req = export_request(None, None, tmp_path / "ledger", parse_ledger_config({}), timestamp=False)
    assert run_export(client, req, labels) == 0
    assert client.calls == ["all"]


@needs_bean_check
def test_yearly_export_passes_bean_check(splits, labels, tmp_path):
    out = tmp_path / "ledger"
    req = export_request(
        None, None, out, parse_ledger_config({}), validate=True, init=True, timestamp=False
    )
    assert run_export(RecordingClient(splits), req, labels) == 0
    assert sorted(p.name for p in out.glob("firefly-*.beancount")) == [
        "firefly-2024.beancount",
        "firefly-2025.beancount",
        "firefly-2026.beancount",
    ]
