"""What must hold whichever way expenses and income are classified (offline)."""

import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from firefly_reports import i18n
from firefly_reports.firefly_client import FireflyClient
from firefly_reports.ledger.accounts import AccountResolver, normalize_component
from firefly_reports.ledger.convert import build_ledger
from firefly_reports.ledger.export import LAYOUT_SINGLE, run_export
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import LedgerConfig, parse_ledger_config
from tests.ledger_helpers import export_request

FIXTURES = Path(__file__).parent / "fixtures"
MAP = {
    "accounts": {"Home Mortgage": "Liabilities:Mortgage"},
    "investment_accounts": {"Acme Investments": "Acme"},
    "operating_currency": ["EUR"],
    "commodities": ["EUR", "USD"],
}
needs_bean_check = pytest.mark.skipif(
    shutil.which("bean-check") is None, reason="bean-check not installed"
)


def load_splits(name):
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return FireflyClient._flatten_transactions(None, payload["data"])  # type: ignore[arg-type]


@pytest.fixture(params=["firefly_transactions.json", "firefly_account_types.json"])
def splits(request):
    return load_splits(request.param)


@pytest.fixture
def labels():
    i18n.load("en")
    return LedgerLabels.from_i18n()


class Client:
    def __init__(self, splits):
        self.splits = splits

    def get_transactions(self, start=None, end=None, tx_type=None):
        return self.splits

    def get_transaction_links(self, resolve_types=True):
        return []


def convert(splits, labels, mode):
    config = parse_ledger_config({**MAP, "classify_by": mode})
    return build_ledger(splits, AccountResolver(config, labels), check_collisions=False)


def balances(ledger, roots):
    totals = defaultdict(lambda: defaultdict(Decimal))
    for tx in ledger.transactions:
        for p in tx.postings:
            if p.account.split(":")[0] in roots:
                totals[p.account][p.amount.currency] += p.amount.number
    return {a: dict(c) for a, c in totals.items()}


def total(ledger, root):
    return sum(
        (p.weight.number for tx in ledger.transactions for p in tx.postings
         if p.account.startswith(root + ":")),
        Decimal(0),
    )  # fmt: skip


def test_default_mode_is_category():
    assert LedgerConfig().classify_by == "category"
    assert parse_ledger_config({}).classify_by == "category"


def test_real_account_balances_identical_between_modes(splits, labels):
    roots = {"Assets", "Liabilities", "Equity"}
    assert balances(convert(splits, labels, "category"), roots) == balances(
        convert(splits, labels, "account"), roots
    )


def test_total_expenses_and_income_identical_between_modes(splits, labels):
    by_category, by_account = (
        convert(splits, labels, "category"),
        convert(splits, labels, "account"),
    )
    for root in ("Expenses", "Income"):
        assert total(by_category, root) == total(by_account, root)


def test_every_transaction_balances_in_both_modes(splits, labels):
    for mode in ("category", "account"):
        for tx in convert(splits, labels, mode).transactions:
            assert all(v == 0 for v in tx.balance().values()), (mode, tx.firefly_id)


def test_no_counterpart_named_accounts_in_category_mode(splits, labels):
    counterparts = {
        normalize_component(str(sp[f"{side}_name"]))
        for sp in splits
        for side, kind in (("source", "revenue"), ("destination", "expense"))
        if str(sp.get(f"{side}_type", "")).lower().startswith(kind)
    }
    categories = {
        normalize_component(str(sp["category_name"])) for sp in splits if sp.get("category_name")
    }
    ledger = convert(splits, labels, "category")
    leaves = {
        p.account.split(":")[-1]
        for tx in ledger.transactions
        for p in tx.postings
        if p.account.startswith(("Expenses:", "Income:"))
    }
    assert leaves <= categories | {"Uncategorized"}
    assert not (leaves & (counterparts - categories))


def test_transfers_never_touch_expenses_or_income(splits, labels):
    transfer_ids = {sp["transaction_journal_id"] for sp in splits if sp["type"] == "transfer"}
    ledger = convert(splits, labels, "category")
    touched = [
        tx.firefly_id
        for tx in ledger.transactions
        if tx.firefly_id in transfer_ids
        and any(p.account.startswith(("Expenses:", "Income:")) for p in tx.postings)
    ]
    assert touched == []


def request(out):
    return export_request(None, None, out, parse_ledger_config(MAP), allow_unmapped=True)


def test_closed_years_are_byte_identical_between_runs(splits, labels, tmp_path):
    out = tmp_path / "ledger"
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    run_export(Client(splits), request(out), labels, now=lambda: t0)
    first = {p.name: p.read_bytes() for p in out.glob("firefly-*.beancount")}
    run_export(Client(splits), request(out), labels, now=lambda: t0 + timedelta(days=30))
    second = {p.name: p.read_bytes() for p in out.glob("firefly-*.beancount")}
    assert first and first == second


def test_all_transactions_are_starred_and_nothing_mentions_reconciliation(splits, labels, tmp_path):
    out = tmp_path / "ledger"
    run_export(Client(splits), request(out), labels)
    text = "".join(p.read_text(encoding="utf-8") for p in out.glob("firefly-*.beancount"))
    headers = re.findall(r"^\d{4}-\d{2}-\d{2} (\S) ", text, re.M)
    assert headers and set(headers) == {"*"}
    assert "reconciled" not in text.lower()


@needs_bean_check
def test_yearly_export_passes_bean_check_including_main(splits, labels, tmp_path):
    out = tmp_path / "ledger"
    req = export_request(
        None, None, out, parse_ledger_config(MAP), allow_unmapped=True, init=True, validate=True
    )
    assert run_export(Client(splits), req, labels) == 0
    import subprocess
    import sys

    run = subprocess.run(
        [sys.executable, "-m", "beancount.scripts.check", str(out / "main.beancount")],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_account_mode_output_matches_the_pre_change_snapshot(labels, tmp_path):
    out = tmp_path / "ledger"
    config = parse_ledger_config({**MAP, "classify_by": "account"})
    req = export_request(None, None, out, config, layout=LAYOUT_SINGLE, timestamp=False)
    run_export(Client(load_splits("firefly_transactions.json")), req, labels)
    snapshot = (FIXTURES / "account_mode_single.beancount").read_text(encoding="utf-8")
    assert (out / "firefly.beancount").read_text(encoding="utf-8") == snapshot
