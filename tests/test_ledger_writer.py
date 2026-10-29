"""Writer-level tests on hand-built ledgers: flag, links, extra metadata, iban (offline)."""

import datetime as dt
from decimal import Decimal

import pytest

from firefly_reports.ledger.errors import ConfigError
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.model import Amount, Ledger, LedgerTransaction, Posting
from firefly_reports.ledger.writers import BeancountWriter, WriterOptions


@pytest.fixture
def labels():
    return LedgerLabels.from_i18n()


def _tx(**kw):
    base = {
        "date": dt.date(2025, 1, 1),
        "narration": "n",
        "postings": (
            Posting("Assets:A", Amount(Decimal("-10.00"), "EUR")),
            Posting("Expenses:B", Amount(Decimal("10.00"), "EUR")),
        ),
        "firefly_id": "1",
    }
    base.update(kw)
    return LedgerTransaction(**base)


def render(ledger, labels):
    return BeancountWriter().render(ledger, WriterOptions(labels=labels))


def test_flag_is_always_star(labels):
    out = render(Ledger((_tx(),)), labels)
    assert '2025-01-01 * "n"' in out
    assert "!" not in out


def test_links_rendered_after_tags(labels):
    out = render(Ledger((_tx(payee="p", tags=("t",), links=("firefly-link-3",)),)), labels)
    assert '2025-01-01 * "p" "n" #t ^firefly-link-3' in out


def test_extra_metadata_on_transaction_and_posting(labels):
    postings = (
        Posting("Assets:A", Amount(Decimal("-10.00"), "EUR")),
        Posting("Expenses:B", Amount(Decimal("10.00"), "EUR"), extra=(("reference", "R1"),)),
    )
    out = render(Ledger((_tx(postings=postings, extra=(("bill", "Affitto"),)),)), labels)
    assert '  bill: "Affitto"\n' in out
    assert '    reference: "R1"\n' in out


def test_posting_payee_metadata(labels):
    postings = (
        Posting("Assets:A", Amount(Decimal("-10.00"), "EUR")),
        Posting("Expenses:B", Amount(Decimal("10.00"), "EUR"), payee="Sports Bar"),
    )
    out = render(Ledger((_tx(postings=postings),)), labels)
    assert '    payee: "Sports Bar"\n' in out


def test_iban_on_open_directive(labels):
    ledger = Ledger((_tx(),), ibans={"Assets:A": "IT00X"})
    out = BeancountWriter().render_accounts(ledger, WriterOptions(labels=labels))
    assert '2025-01-01 open Assets:A\n  iban: "IT00X"\n' in out
    assert "open Expenses:B\n  iban" not in out


def test_by_year_does_not_carry_ibans_but_accounts_file_uses_full_ledger(labels):
    ledger = Ledger((_tx(),), ibans={"Assets:A": "IT00X"})
    assert ledger.by_year()[2025].ibans == {}


@pytest.mark.parametrize("fixed", ["bill", "reference", "external_id", "iban", "payee"])
def test_labels_reject_override_of_fixed_keys(fixed):
    with pytest.raises(ConfigError):
        LedgerLabels.from_i18n({"category": fixed})
