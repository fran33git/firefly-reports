"""Conversion with expenses/income classified by Firefly category (offline)."""

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from firefly_reports.firefly_client import FireflyClient
from firefly_reports.ledger.accounts import AccountResolver
from firefly_reports.ledger.convert import build_ledger
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import parse_ledger_config

FIXTURE = Path(__file__).parent / "fixtures" / "firefly_transactions.json"
D = Decimal


def split(jid, typ, src, src_type, dst, dst_type, amount="10.00", **extra):
    base = {
        "type": typ,
        "date": "2025-01-01",
        "amount": amount,
        "currency_code": "EUR",
        "source_name": src,
        "source_type": src_type,
        "destination_name": dst,
        "destination_type": dst_type,
        "transaction_journal_id": jid,
        "group_id": jid,
        "description": "d",
    }
    base.update(extra)
    return base


def withdrawal(jid, category="Bar", dst="Bar Sport", amount="10.00", **extra):
    return split(
        jid, "withdrawal", "Conto", "Asset account", dst, "Expense account", amount,
        category_name=category, **extra,
    )  # fmt: skip


def deposit(jid, category="Fatture", src="Cliente", amount="10.00", **extra):
    return split(
        jid, "deposit", src, "Revenue account", "Conto", "Asset account", amount,
        category_name=category, **extra,
    )  # fmt: skip


def convert(splits, mode="category", links=(), **config):
    resolver = AccountResolver(
        parse_ledger_config({"classify_by": mode, **config}), LedgerLabels.from_i18n()
    )
    return build_ledger(splits, resolver, check_collisions=False, links=links)


def accounts_of(tx):
    return [p.account for p in tx.postings]


def test_withdrawal_posts_to_category_account():
    (tx,) = convert([withdrawal("1")]).transactions
    assert accounts_of(tx) == ["Assets:Conto", "Expenses:Bar"]
    assert tx.payee == "Bar Sport"
    assert tx.category is None and all(p.category is None for p in tx.postings)


def test_deposit_posts_to_income_category():
    (tx,) = convert([deposit("1")]).transactions
    assert accounts_of(tx) == ["Income:Fatture", "Assets:Conto"]
    assert tx.postings[0].amount.number == D("-10.00")


def test_missing_category_goes_to_uncategorized():
    (tx,) = convert([withdrawal("1", category=None)]).transactions
    assert accounts_of(tx) == ["Assets:Conto", "Expenses:Uncategorized"]


def test_mapped_category_uses_mapping():
    config = {"categories": {"expense": {"Bar": "Expenses:Tempo-Libero:Bar"}}}
    (tx,) = convert([withdrawal("1")], **config).transactions
    assert accounts_of(tx) == ["Assets:Conto", "Expenses:Tempo-Libero:Bar"]


def test_transfer_has_no_category_posting_and_keeps_metadata():
    sp = split("1", "transfer", "Conto", "Asset account", "Risparmio", "Asset account",
               category_name="Giroconti")  # fmt: skip
    (tx,) = convert([sp]).transactions
    assert accounts_of(tx) == ["Assets:Conto", "Assets:Risparmio"]
    assert tx.category == "Giroconti"


def test_withdrawal_to_cash_account_is_two_real_sides():
    sp = split("1", "withdrawal", "Conto", "Asset account", "Contanti", "Cash account",
               category_name="Prelievi")  # fmt: skip
    (tx,) = convert([sp]).transactions
    assert accounts_of(tx) == ["Assets:Conto", "Assets:Cash"]
    assert tx.category == "Prelievi"


def test_withdrawal_from_a_liability_posts_category_on_the_other_side():
    sp = split("1", "withdrawal", "Mutuo", "Loan", "Idraulico", "Expense account",
               category_name="Casa")  # fmt: skip
    (tx,) = convert([sp]).transactions
    assert accounts_of(tx) == ["Liabilities:Mutuo", "Expenses:Casa"]


def test_two_counterpart_sides_fall_back_to_account_behaviour():
    sp = split("1", "withdrawal", "Negozio A", "Expense account", "Negozio B", "Expense account",
               category_name="X")  # fmt: skip
    (tx,) = convert([sp]).transactions
    assert accounts_of(tx) == ["Expenses:Negozio-A", "Expenses:Negozio-B"]


def test_split_group_two_categories_two_rows_and_balances():
    g = {"group_id": "G", "group_title": "Spesa"}
    splits = [
        withdrawal("1", "Cibo", "Esselunga", "10.00", **g),
        withdrawal("2", "Casa", "Esselunga", "20.00", **g),
    ]
    (tx,) = convert(splits).transactions
    assert accounts_of(tx) == ["Assets:Conto", "Expenses:Cibo", "Expenses:Casa"]
    assert [p.amount.number for p in tx.postings] == [D("-30.00"), D("10.00"), D("20.00")]
    assert all(v == 0 for v in tx.balance().values())
    assert tx.payee == "Esselunga" and all(p.payee is None for p in tx.postings)


def test_diverging_counterparts_put_payee_on_category_postings():
    g = {"group_id": "G", "group_title": "Spesa divisa"}
    splits = [
        withdrawal("1", "Cibo", "Negozio A", "10.00", **g),
        withdrawal("2", "Cibo", "Negozio B", "20.00", **g),
    ]
    (tx,) = convert(splits).transactions
    assert tx.payee is None
    rows = [(p.account, p.amount.number, p.payee) for p in tx.postings]
    assert rows == [
        ("Assets:Conto", D("-30.00"), None),
        ("Expenses:Cibo", D("10.00"), "Negozio A"),
        ("Expenses:Cibo", D("20.00"), "Negozio B"),
    ]


def test_same_category_and_counterpart_splits_are_summed():
    g = {"group_id": "G"}
    splits = [withdrawal("1", "Cibo", "A", "10.00", **g), withdrawal("2", "Cibo", "A", "5.00", **g)]
    (tx,) = convert(splits).transactions
    assert [(p.account, p.amount.number) for p in tx.postings] == [
        ("Assets:Conto", D("-15.00")),
        ("Expenses:Cibo", D("15.00")),
    ]


def test_diverging_notes_stay_on_the_category_postings():
    g = {"group_id": "G"}
    splits = [
        withdrawal("1", "Cibo", "A", "10.00", notes="uno", **g),
        withdrawal("2", "Casa", "A", "5.00", notes="due", **g),
    ]
    (tx,) = convert(splits).transactions
    assert tx.note is None
    assert [p.note for p in tx.postings] == [None, "uno", "due"]


def test_foreign_amount_price_on_category_posting():
    sp = withdrawal("1", amount="10.00", foreign_amount="11.00", foreign_currency_code="USD")
    (tx,) = convert([sp]).transactions
    cat = tx.postings[1]
    assert cat.account == "Expenses:Bar"
    assert (cat.amount.number, cat.amount.currency) == (D("11.00"), "USD")
    assert (cat.price_total.number, cat.price_total.currency) == (D("10.00"), "EUR")


def test_deposit_foreign_amount_price_on_income_category_posting():
    sp = deposit("1", amount="92.00", foreign_amount="100.00", foreign_currency_code="USD")
    (tx,) = convert([sp]).transactions
    cat = tx.postings[0]
    assert cat.account == "Income:Fatture" and cat.amount.number == D("-100.00")
    assert cat.price_total.number == D("92.00")


def test_account_mode_is_unchanged():
    (tx,) = convert([withdrawal("1")], mode="account").transactions
    assert accounts_of(tx) == ["Assets:Conto", "Expenses:Bar-Sport"]
    assert tx.category == "Bar" and tx.payee == "Bar Sport"


def _balances(ledger, roots):
    totals = defaultdict(lambda: defaultdict(Decimal))
    for tx in ledger.transactions:
        for p in tx.postings:
            if p.account.split(":")[0] in roots:
                totals[p.account][p.amount.currency] += p.amount.number
    return {a: dict(c) for a, c in totals.items()}


@pytest.fixture
def fixture_splits():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return FireflyClient._flatten_transactions(None, payload["data"])  # type: ignore[arg-type]


def test_real_account_balances_equal_in_both_modes(fixture_splits):
    by_category = convert(fixture_splits, "category")
    by_account = convert(fixture_splits, "account")
    roots = {"Assets", "Liabilities", "Equity"}
    assert _balances(by_category, roots) == _balances(by_account, roots)


def test_total_of_expenses_and_income_equal_in_both_modes(fixture_splits):
    def total(ledger, root):
        return sum(
            (p.weight.number for tx in ledger.transactions for p in tx.postings
             if p.account.startswith(root + ":")),
            Decimal(0),
        )  # fmt: skip

    for root in ("Expenses", "Income"):
        assert total(convert(fixture_splits, "category"), root) == total(
            convert(fixture_splits, "account"), root
        )
