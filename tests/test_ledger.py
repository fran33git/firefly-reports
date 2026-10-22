"""Tests for the ledger (Beancount) export: normalisation, mapping, writer, validation."""

import json
import shutil
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
import responses as rsps_lib

from firefly_reports import i18n
from firefly_reports.firefly_client import FireflyClient
from firefly_reports.ledger.accounts import AccountResolver, classify, normalize_component
from firefly_reports.ledger.convert import build_ledger, normalize_tag
from firefly_reports.ledger.errors import (
    AccountCollisionError,
    ConfigError,
    ConversionError,
    LedgerError,
)
from firefly_reports.ledger.export import (
    init_ledger_files,
    render_main_beancount,
    run_export,
)
from firefly_reports.ledger.labels import META_KEY_RE, LedgerLabels
from firefly_reports.ledger.mapping import LedgerConfig, load_ledger_config, parse_ledger_config
from firefly_reports.ledger.validate import run_bean_check
from firefly_reports.ledger.writers import BeancountWriter, WriterOptions, atomic_write
from firefly_reports.ledger.writers.beancount import format_number, quote
from tests.ledger_helpers import export_request

FIXTURE = Path(__file__).parent / "fixtures" / "firefly_transactions.json"
BASE = "https://firefly.test"

MAP = {
    "classify_by": "account",  # these tests pin the counterpart-account naming rules
    "accounts": {"Mutuo Casa": "Liabilities:Mutuo"},
    "investment_accounts": {"Fineco Investimenti": "Fineco"},
    "operating_currency": ["EUR"],
    "commodities": ["EUR", "USD"],
}


@pytest.fixture
def labels():
    return LedgerLabels.from_i18n()


@pytest.fixture
def config():
    return parse_ledger_config(MAP)


@pytest.fixture
def splits():
    """Flat splits exactly as FireflyClient returns them (paginated, no date filter)."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with rsps_lib.RequestsMock() as mock:
        mock.add(rsps_lib.GET, f"{BASE}/api/v1/transactions", json=payload)
        result = FireflyClient(BASE, "tok", request_delay=0).get_transactions()
        assert "start" not in mock.calls[0].request.params
    return result


@pytest.fixture
def ledger(splits, config, labels):
    return build_ledger(splits, AccountResolver(config, labels))


def render(ledger, labels, config=None, stamp=None):
    options = WriterOptions(
        labels=labels,
        commodities=config.commodities if config else (),
        generated_at=stamp,
    )
    return BeancountWriter().render(ledger, options)


def tx_by_id(ledger, firefly_id):
    return next(t for t in ledger.transactions if t.firefly_id == firefly_id)


# ---------- normalisation ----------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Conto Corrente", "Conto-Corrente"),
        ("Caffè Münch & Söhne", "Caffe-Munch-Sohne"),
        ("straße ø æ ł", "Strasse-o-ae-l"),
        ("  --risparmio--  ", "Risparmio"),
        ("2025 budget", "2025-budget"),
        ("été", "Ete"),
        ("???", ""),
        ("", ""),
    ],
)
def test_normalize_component(raw, expected):
    assert normalize_component(raw) == expected


def test_classify_firefly_types():
    assert classify("Asset account") == "asset"
    assert classify("Revenue account") == "income"
    assert classify("Mortgage") == "liability"
    assert classify("Initial balance account") == "opening"
    assert classify("weird") == "unknown"
    assert classify(None) == "unknown"


def test_classify_liability_credit_and_auxiliary_accounts():
    # Firefly's counterpart of liability opening balances: Equity, like asset ones.
    assert classify("Liability credit account") == "opening"
    assert classify("Liability credit") == "opening"  # type string of older Firefly versions
    # "Import account" is Firefly's technical counterpart for imports, not real money.
    assert classify("Import account") == "import"
    # A regular asset account in Firefly: a cash-flow account, not a liability.
    assert classify("Credit card") == "asset"


@pytest.mark.parametrize(
    "firefly_type, kind",
    [
        ("Asset account", "asset"),
        ("Expense account", "expense"),
        ("Revenue account", "income"),
        ("Cash account", "cash"),
        ("Initial balance account", "opening"),
        ("Reconciliation account", "reconciliation"),
        ("Loan", "liability"),
        ("Debt", "liability"),
        ("Mortgage", "liability"),
        ("Credit card", "asset"),
        ("Liability credit account", "opening"),
        ("Import account", "import"),
    ],
)
def test_classify_every_firefly_api_type(firefly_type, kind):
    assert classify(firefly_type) == kind


def test_liability_credit_split_goes_to_opening_balances(config, labels):
    sp = _split("20", "Liability credit", "Mutuo Casa", source_type="Liability credit account")
    tx = build_ledger([sp], AccountResolver(config, labels)).transactions[0]
    assert tx.postings[0].account == "Equity:Opening-Balances"
    assert tx.postings[1].account == "Liabilities:Mutuo"


def test_import_account_resolves_to_equity_imports(config, labels):
    sp = _split("21", "Import Conto", "Supermercato Più", source_type="Import account")
    tx = build_ledger([sp], AccountResolver(config, labels)).transactions[0]
    assert tx.postings[0].account == "Equity:Imports"


def test_import_account_can_be_remapped_explicitly(labels):
    cfg = parse_ledger_config({"accounts": {"Import Conto": "Assets:Banca:Import"}})
    sp = _split("21", "Import Conto", "Supermercato Più", source_type="Import account")
    resolver = AccountResolver(cfg, labels)
    tx = build_ledger([sp], resolver).transactions[0]
    assert tx.postings[0].account == "Assets:Banca:Import"
    assert resolver.warnings()  # Equity expected for the type, Assets chosen: reported


def test_normalize_tag():
    assert normalize_tag("tasse 2025") == "tasse-2025"
    assert normalize_tag("a/b.c_d") == "a/b.c_d"
    assert normalize_tag("  ") == ""


def test_resolver_roots_and_special_accounts(config, labels):
    r = AccountResolver(parse_ledger_config(None), labels)
    assert r.resolve("Mio Conto", "Asset account") == "Assets:Mio-Conto"
    assert r.resolve("Amazon", "Expense account") == "Expenses:Amazon"
    assert r.resolve("Cliente", "Revenue account") == "Income:Cliente"
    assert r.resolve("Mutuo", "Mortgage") == "Liabilities:Mutuo"
    assert r.resolve("x initial balance", "Initial balance account") == "Equity:Opening-Balances"
    assert r.resolve("Reconciliation (X)", "Reconciliation account") == "Equity:Reconciliation"
    assert r.resolve("(cash)", "Cash account") == "Assets:Cash"


def test_resolver_override_investment_and_fallback(labels):
    cfg = parse_ledger_config(
        {
            "accounts": {"7": "Assets:Sette"},
            "investment_accounts": {"Broker X": "Banca Ünica"},
            "fallback": {"expense": "Expenses:Altro"},
        }
    )
    r = AccountResolver(cfg, labels)
    assert r.resolve("Qualsiasi", "Asset account", 7) == "Assets:Sette"  # match by id
    assert r.resolve("Broker X", "Asset account") == f"{labels.investment_root}:Banca-Unica:Cash"
    assert r.resolve("(no name)", "Expense account") == "Expenses:Altro"
    assert r.resolve("", "Revenue account") == labels.fallback_income


def test_resolver_strict_fallback(labels):
    cfg = parse_ledger_config({"accounts": {"Bar": "Expenses:Bar"}, "fallback": {"strict": True}})
    r = AccountResolver(cfg, labels)
    assert r.resolve("Bar", "Expense account") == "Expenses:Bar"
    assert r.resolve("Altro", "Expense account") == labels.fallback_expense
    assert r.resolve("Conto", "Asset account") == "Assets:Conto"  # strict only hits expense/income


def test_collision_is_an_explicit_error(labels):
    r = AccountResolver(parse_ledger_config(None), labels)
    r.resolve("Conto A", "Asset account")
    r.resolve("Conto-A", "Asset account")
    r.resolve("Conto A", "Asset account")  # same account twice is fine
    with pytest.raises(AccountCollisionError) as exc:
        r.raise_on_collisions()
    assert "Assets:Conto-A" in str(exc.value)
    assert "'Conto A'" in str(exc.value)


def test_collision_between_auto_name_and_explicit_mapping(labels):
    cfg = parse_ledger_config({"accounts": {"Cassa": "Assets:Contanti"}})
    r = AccountResolver(cfg, labels)
    r.resolve("Cassa", "Asset account")
    r.resolve("Contanti", "Asset account")
    with pytest.raises(AccountCollisionError):
        r.raise_on_collisions()


def test_explicit_many_to_one_mapping_is_allowed(labels):
    cfg = parse_ledger_config({"accounts": {"A": "Assets:X", "B": "Assets:X"}})
    r = AccountResolver(cfg, labels)
    r.resolve("A", "Asset account")
    r.resolve("B", "Asset account")
    r.raise_on_collisions()


def test_explicit_mapping_by_id_wins_over_name(labels):
    cfg = parse_ledger_config(
        {"accounts": {"PayPal": "Expenses:Fees:PayPal", "5": "Assets:PayPal"}}
    )
    r = AccountResolver(cfg, labels)
    assert r.resolve("PayPal", "Asset account", 5) == "Assets:PayPal"
    assert r.warnings() == []  # id match: the name-based entry is never considered


def test_cross_root_name_mapping_is_kept_with_a_warning(labels):
    cfg = parse_ledger_config({"accounts": {"PayPal": "Expenses:Fees:PayPal"}})
    r = AccountResolver(cfg, labels)
    # not an error: the explicit mapping stays valid, but the user is warned
    assert r.resolve("PayPal", "Asset account", 5) == "Expenses:Fees:PayPal"
    assert r.warnings() == [("PayPal", "Asset account", "Expenses:Fees:PayPal")]
    # coherent root: no warning
    coherent = AccountResolver(parse_ledger_config({"accounts": {"Banca": "Assets:Banca"}}), labels)
    assert coherent.resolve("Banca", "Asset account") == "Assets:Banca"
    assert coherent.warnings() == []


def test_collision_aborts_build_ledger(labels):
    splits = [
        _split("1", "Conto A", "Conto-A"),
        _split("2", "Conto-A", "Conto A"),
    ]
    with pytest.raises(AccountCollisionError):
        build_ledger(splits, AccountResolver(parse_ledger_config(None), labels))


# ---------- mapping config ----------


def test_config_rejects_unknown_keys_and_bad_values():
    with pytest.raises(ConfigError):
        parse_ledger_config({"acounts": {}})
    with pytest.raises(ConfigError):
        parse_ledger_config({"accounts": {"A": "Cash:Wallet"}})
    with pytest.raises(ConfigError):
        parse_ledger_config({"accounts": {"A": "Assets:lower"}})
    with pytest.raises(ConfigError):
        parse_ledger_config({"commodities": ["eur$"]})
    with pytest.raises(ConfigError):
        parse_ledger_config({"labels": {"colour": "x"}})
    with pytest.raises(ConfigError):
        parse_ledger_config({"fallback": {"oops": "Expenses:X"}})
    with pytest.raises(ConfigError):
        parse_ledger_config(["not", "a", "mapping"])
    with pytest.raises(ConfigError):
        parse_ledger_config({"accounts": ["list"]})
    with pytest.raises(ConfigError):
        parse_ledger_config({"investment_accounts": {"X": ""}})


def test_config_uppercases_currencies_and_dedups():
    cfg = parse_ledger_config({"operating_currency": ["eur", "EUR"], "commodities": ["usd"]})
    assert cfg.operating_currency == ("EUR",)
    assert cfg.commodities == ("USD",)


def test_config_rejects_non_boolean_strict():
    # bool("false") is True: only a real YAML boolean may enable strict mode
    with pytest.raises(ConfigError):
        parse_ledger_config({"fallback": {"strict": "false"}})
    with pytest.raises(ConfigError):
        parse_ledger_config({"fallback": {"strict": 0}})
    with pytest.raises(ConfigError):
        parse_ledger_config({"fallback": {"strict": "yes"}})
    assert parse_ledger_config({"fallback": {"strict": True}}).fallback_strict is True
    assert parse_ledger_config({"fallback": {"strict": False}}).fallback_strict is False
    assert parse_ledger_config({}).fallback_strict is False


def test_config_rejects_keys_colliding_after_str(tmp_path):
    # YAML '12:' (int) and "'12':" (string) overwrite each other silently
    text = "accounts:\n  12: 'Assets:Dodici'\n  '12': 'Assets:Altro'\n"
    path = tmp_path / "map.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_ledger_config(path)
    assert "'12'" in str(exc.value)
    direct = {12: "Assets:Dodici", "12": "Assets:Altro"}
    with pytest.raises(ConfigError):
        parse_ledger_config({"accounts": direct})


def test_load_config_from_yaml_file(tmp_path):
    path = tmp_path / "map.yaml"
    path.write_text("accounts:\n  12: 'Assets:Dodici'\n", encoding="utf-8")
    assert load_ledger_config(path).accounts == {"12": "Assets:Dodici"}
    assert load_ledger_config(None) == LedgerConfig()
    path.write_text("accounts: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_ledger_config(path)
    with pytest.raises(ConfigError):
        load_ledger_config(tmp_path / "missing.yaml")


def test_shipped_example_mapping_is_valid():
    cfg = load_ledger_config(Path(__file__).parent.parent / "beancount_map.example.yaml")
    assert cfg.investment_accounts == {"Fineco Investimenti": "Fineco"}


# ---------- conversion ----------


def _split(jid, src, dst, amount="10.00", **extra):
    base = {
        "type": "withdrawal",
        "date": "2025-01-01",
        "amount": amount,
        "currency_code": "EUR",
        "source_name": src,
        "source_type": "Asset account",
        "destination_name": dst,
        "destination_type": "Expense account",
        "transaction_journal_id": jid,
        "group_id": jid,
        "description": "d",
    }
    base.update(extra)
    return base


def test_every_transaction_balances_per_currency(ledger):
    for tx in ledger.transactions:
        assert all(v == 0 for v in tx.balance().values()), tx.firefly_id


def test_amounts_are_decimal(ledger):
    for tx in ledger.transactions:
        for p in tx.postings:
            assert isinstance(p.amount.number, Decimal)


def test_withdrawal_destination_plus_source_minus(ledger):
    tx = tx_by_id(ledger, "3")
    src, dst = tx.postings
    assert (src.account, src.amount.number) == ("Assets:Conto-Corrente", Decimal("-42.50"))
    assert (dst.account, dst.amount.number) == ("Expenses:Caffe-Munch-Sohne", Decimal("42.50"))
    assert tx.payee == "Caffè Münch & Söhne"
    assert tx.category == "Ristoranti" and tx.budget == "Svago"


def test_deposit_and_tags(ledger):
    tx = tx_by_id(ledger, "2")
    assert tx.tags == ("fattura", "tasse-2025")
    assert tx.postings[0].account == "Income:Rossi-S-r-l"
    assert tx.postings[1].amount.number == Decimal("3200.00")


def test_transfer_has_no_payee(ledger):
    tx = tx_by_id(ledger, "4")
    assert tx.payee is None
    assert [p.account for p in tx.postings] == [
        "Assets:Conto-Corrente",
        "Assets:Risparmio-Emergenza",
    ]


def test_multi_split_group_is_one_transaction(ledger):
    tx = tx_by_id(ledger, "5")
    assert tx.firefly_group_id == "5"
    assert tx.narration == "Spesa del sabato"
    # three splits, one shared source -> aggregated into a single -49.50 posting
    assert len(tx.postings) == 4
    assert tx.postings[0].amount.number == Decimal("-49.50")
    assert {p.account for p in tx.postings[1:]} == {
        "Expenses:Supermercato-Piu",
        "Expenses:Farmacia-Centrale",
    }
    # category differs across splits -> per-posting metadata, none at transaction level
    assert tx.category is None
    assert sum(p.amount.number for p in tx.postings) == 0
    # the two splits towards the same supermarket stay distinct: they carry different metadata
    assert [p.category for p in tx.postings[1:]] == ["Alimentari", "Casa", "Salute"]


def test_foreign_amount_withdrawal_uses_total_price(ledger):
    tx = tx_by_id(ledger, "8")
    src, dst = tx.postings
    assert src.amount.number == Decimal("-91.75") and src.amount.currency == "EUR"
    assert dst.amount.number == Decimal("100.00") and dst.amount.currency == "USD"
    assert dst.price_total.number == Decimal("91.75") and dst.price_total.currency == "EUR"


def test_foreign_amount_deposit_puts_foreign_on_revenue_side(ledger):
    tx = tx_by_id(ledger, "9")
    src, dst = tx.postings
    assert src.account == "Income:Freelance-USA-Inc"
    assert src.amount.number == Decimal("-200.00") and src.amount.currency == "USD"
    assert src.price_total.number == Decimal("184.20")
    assert dst.amount.currency == "EUR" and dst.amount.number == Decimal("184.20")
    assert tx.balance() == {"EUR": Decimal("0.00")}


def test_foreign_currency_same_as_base_is_ignored(config, labels):
    sp = _split("1", "A", "B", foreign_amount="10.00", foreign_currency_code="eur")
    tx = build_ledger([sp], AccountResolver(config, labels)).transactions[0]
    assert all(p.price_total is None for p in tx.postings)
    assert {p.amount.currency for p in tx.postings} == {"EUR"}


def test_invalid_foreign_currency_code_is_rejected(config, labels):
    # '1inch' uppercased would render as '@@ ... 1INCH', a bean-check syntax error.
    sp = _split("1", "A", "B", foreign_amount="10.00", foreign_currency_code="1inch")
    with pytest.raises(ConversionError, match="1INCH"):
        build_ledger([sp], AccountResolver(config, labels))


def test_opening_balance_and_reconciliation_use_equity(ledger):
    assert tx_by_id(ledger, "1").postings[0].account == "Equity:Opening-Balances"
    assert tx_by_id(ledger, "11").postings[0].account == "Equity:Reconciliation"


def test_investment_account_maps_to_broker_cash(ledger, labels):
    tx = tx_by_id(ledger, "10")
    assert tx.postings[1].account == f"{labels.investment_root}:Fineco:Cash"


def test_placeholder_and_cash_counterparts(ledger, labels):
    assert tx_by_id(ledger, "12").postings[1].account == labels.fallback_expense
    assert tx_by_id(ledger, "12").payee is None
    assert tx_by_id(ledger, "13").postings[1].account == "Assets:Cash"


def test_liability_source(ledger):
    assert tx_by_id(ledger, "14").postings[0].account == "Liabilities:Mutuo"


def test_ordering_is_by_date_then_numeric_id(config, labels):
    splits = [
        _split("10", "A", "B", date="2025-01-02"),
        _split("9", "A", "B", date="2025-01-02"),
        _split("100", "A", "B", date="2025-01-01"),
    ]
    ledger = build_ledger(splits, AccountResolver(config, labels))
    assert [t.firefly_id for t in ledger.transactions] == ["100", "9", "10"]


def test_invalid_input_raises_conversion_error(config, labels):
    r = lambda: AccountResolver(config, labels)  # noqa: E731
    with pytest.raises(ConversionError):
        build_ledger([_split("1", "A", "B", amount="abc")], r())
    with pytest.raises(ConversionError):
        build_ledger([_split("1", "A", "B", amount="NaN")], r())
    with pytest.raises(ConversionError):
        build_ledger([_split("1", "A", "B", amount=None)], r())
    with pytest.raises(ConversionError):
        build_ledger([_split("1", "A", "B", currency_code="")], r())
    with pytest.raises(ConversionError):
        build_ledger([_split("1", "A", "B", date="oggi")], r())


def test_invalid_currency_code_raises_conversion_error(config, labels):
    # '1inch' uppercased would render as 'commodity 1INCH', a bean-check syntax error.
    bad = _split("1", "A", "B", currency_code="1inch")
    with pytest.raises(ConversionError) as exc:
        build_ledger([bad], AccountResolver(config, labels))
    assert "1INCH" in str(exc.value)
    # valid codes still pass (uppercased, as before)
    ok = _split("2", "A", "B", currency_code="eur")
    tx = build_ledger([ok], AccountResolver(config, labels)).transactions[0]
    assert all(p.amount.currency == "EUR" for p in tx.postings)


def test_no_float_is_ever_used(config, labels):
    # 0.1 + 0.2 style amounts stay exact because everything goes through Decimal(str)
    sp = [_split("1", "A", "B", amount="0.10"), _split("2", "A", "B", amount="0.20", group_id="1")]
    tx = build_ledger(sp, AccountResolver(config, labels)).transactions[0]
    assert tx.postings[0].amount.number == Decimal("-0.30")


def test_unbalanced_foreign_split_raises_conversion_error(config, labels):
    # A foreign amount with the opposite sign of the base amount breaks the @@
    # price symmetry (the price is the absolute value), leaving a residual in
    # the base currency.
    sp = _split("1", "A", "B", amount="10.00", foreign_currency_code="USD", foreign_amount="-12.00")
    with pytest.raises(ConversionError) as exc:
        build_ledger([sp], AccountResolver(config, labels))
    assert "does not balance" in str(exc.value)


# ---------- writer ----------


def test_quote_escapes_quotes_backslashes_newlines():
    assert quote('say "hi"') == '"say \\"hi\\""'
    assert quote("a\\b") == '"a\\\\b"'
    assert quote("l1\nl2\r\nl3") == '"l1 l2 l3"'
    assert quote("  padded ") == '"padded"'


def test_format_number_never_scientific():
    assert format_number(Decimal("1E+3")) == "1000"
    assert format_number(Decimal("0.00000001")) == "0.00000001"
    assert format_number(Decimal("-12.50")) == "-12.50"


def test_output_structure(ledger, labels, config):
    out = render(ledger, labels, config, stamp=datetime(2026, 1, 2, 3, 4, 5).astimezone())
    lines = out.splitlines()
    assert lines[0] == f"; {labels.header_notice}"
    assert lines[1].startswith("; Generated: 20")
    assert "2024-12-31 commodity EUR" in out
    assert "2025-03-03 commodity USD" in out
    assert "2024-12-31 open Equity:Opening-Balances" in out
    assert "2024-12-31 open Assets:Conto-Corrente" in out
    first_tx = out.index(" * ")
    assert out.index("commodity EUR") < first_tx and out.index(" open ") < first_tx
    assert out.endswith("\n") and not out.endswith("\n\n")


def test_open_date_is_first_use(ledger, labels):
    out = render(ledger, labels)
    assert "2025-03-03 open Expenses:Hotel-Lisboa" in out
    assert "2024-12-31 open Assets:Conto-Corrente" in out


def test_transaction_text(ledger, labels):
    out = render(ledger, labels)
    assert '2025-01-15 * "Rossi S.r.l." "Fattura #001" #fattura #tasse-2025' in out
    assert 'firefly_id: "2"' in out
    assert '2025-01-20 * "Caffè Münch & Söhne" "Cena \\"da Mario\\""' in out
    assert "  categoria" not in out  # English labels in tests
    assert '  category: "Ristoranti"' in out
    assert '  budget: "Svago"' in out
    assert '  note: "Riga uno Riga due con \\\\ backslash"' in out
    assert "100.00 USD @@ 91.75 EUR" in out
    assert '  firefly_group_id: "5"' in out


def test_deterministic_byte_for_byte(splits, config, labels):
    def once():
        led = build_ledger(list(splits), AccountResolver(config, labels))
        return render(led, labels, config)

    assert once() == once()
    shuffled = list(reversed(splits))
    led = build_ledger(shuffled, AccountResolver(config, labels))
    assert render(led, labels, config) == once()


def test_yearly_files_carry_no_timestamp(config, labels, ledger):
    writer = BeancountWriter()

    def yearly(generated_at):
        options = WriterOptions(
            labels=labels, commodities=config.commodities, generated_at=generated_at
        )
        return {
            year: writer.render_transactions(year_ledger, options)
            for year, year_ledger in ledger.by_year().items()
        }

    # different run times must not rewrite the per-year files (closed years never change)
    first = yearly(datetime(2026, 1, 2, 3, 4, 5).astimezone())
    second = yearly(datetime(2027, 6, 7, 8, 9, 10).astimezone())
    assert first == second
    assert first and all("; Generated:" not in content for content in first.values())
    # the timestamp stays in accounts.beancount and in the single-file layout
    stamp = datetime(2026, 1, 2, 3, 4, 5).astimezone()
    options = WriterOptions(labels=labels, commodities=config.commodities, generated_at=stamp)
    assert "; Generated:" in writer.render_accounts(ledger, options)
    assert "; Generated:" in writer.render(ledger, options)
    # --no-timestamp (generated_at=None) omits it everywhere
    plain = WriterOptions(labels=labels, commodities=config.commodities, generated_at=None)
    assert "; Generated:" not in writer.render_accounts(ledger, plain)
    assert "; Generated:" not in writer.render(ledger, plain)


def test_empty_ledger_renders_header_only(labels):
    from firefly_reports.ledger.model import Ledger

    assert render(Ledger(()), labels) == f"; {labels.header_notice}\n"


def test_atomic_write_replaces_and_leaves_no_temp(tmp_path):
    target = tmp_path / "sub" / "firefly.beancount"
    atomic_write(target, "one\n")
    atomic_write(target, "two\n")
    assert target.read_text() == "two\n"
    assert [p.name for p in target.parent.iterdir()] == ["firefly.beancount"]


def test_atomic_write_failure_keeps_old_file(tmp_path, monkeypatch):
    target = tmp_path / "f.beancount"
    target.write_text("old\n")
    monkeypatch.setattr("os.replace", lambda *a: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        atomic_write(target, "new\n")
    assert target.read_text() == "old\n"
    assert [p.name for p in tmp_path.iterdir()] == ["f.beancount"]


# ---------- i18n ----------


def test_metadata_keys_are_valid_in_every_language():
    try:
        for lang in ("en", "it"):
            i18n.load(lang)
            labels = LedgerLabels.from_i18n()
            for key in (labels.meta_category, labels.meta_budget, labels.meta_note):
                assert META_KEY_RE.match(key), (lang, key)
    finally:
        i18n.load("en")


def test_italian_output_and_technical_keys_stay_fixed(splits, config):
    try:
        i18n.load("it")
        labels = LedgerLabels.from_i18n()
        out = render(build_ledger(splits, AccountResolver(config, labels)), labels)
    finally:
        i18n.load("en")
    assert out.startswith("; GENERATO - NON MODIFICARE A MANO")
    assert '  categoria: "Ristoranti"' in out
    assert '  nota: "' in out
    assert 'firefly_id: "3"' in out
    assert "Assets:Investimenti:Fineco:Cash" in out


def test_label_overrides_and_validation():
    labels = LedgerLabels.from_i18n({"category": "categoria"})
    assert labels.meta_category == "categoria"
    with pytest.raises(ConfigError):
        LedgerLabels.from_i18n({"category": "Categoria"})
    with pytest.raises(ConfigError):
        LedgerLabels.from_i18n({"note": "nòta"})


def test_label_overrides_reject_duplicate_and_reserved_keys():
    # equal keys would emit duplicate metadata fields -> 'Duplicate metadata field' in bean-check
    with pytest.raises(ConfigError):
        LedgerLabels.from_i18n({"category": "cat", "budget": "cat"})
    with pytest.raises(ConfigError):
        LedgerLabels.from_i18n({"note": "budget"})  # clashes with the default budget key
    # the firefly id keys are written on every transaction and cannot be reused
    with pytest.raises(ConfigError):
        LedgerLabels.from_i18n({"category": "firefly_id"})
    with pytest.raises(ConfigError):
        LedgerLabels.from_i18n({"budget": "firefly_group_id"})


def test_error_messages_follow_active_language():
    err = ConversionError("ledger.err_date", id="5", value="x")
    assert "invalid date" in str(err)
    try:
        i18n.load("it")
        assert "data non valida" in str(err)
    finally:
        i18n.load("en")


# ---------- export orchestration ----------


class FakeClient:
    def __init__(self, splits):
        self.splits = splits
        self.calls = []

    def get_transactions(self, start=None, end=None, tx_type=None):
        self.calls.append((start, end, tx_type))
        return self.splits

    def get_transaction_links(self, resolve_types=True):
        return []


def test_run_export_writes_file_and_init_never_overwrites(tmp_path, splits, config, labels):
    out = tmp_path / "ledger"
    out.mkdir()
    (tmp_path / "ledger" / "investments.beancount").write_text("; mine\n")
    (tmp_path / "ledger" / "main.beancount").write_text("; keep me\n")
    client = FakeClient(splits)
    req = export_request(None, None, out, config, layout="single", init=True, timestamp=False)
    assert run_export(client, req, labels) == 0
    assert client.calls == [(None, None, "all")]
    assert (out / "firefly.beancount").read_text().startswith("; GENERATED")
    assert (tmp_path / "ledger" / "main.beancount").read_text() == "; keep me\n"
    assert (tmp_path / "ledger" / "investments.beancount").read_text() == "; mine\n"
    assert (tmp_path / "ledger" / "prices.beancount").exists()


def test_init_creates_main_with_includes_and_options(tmp_path, ledger, config):
    created = init_ledger_files(tmp_path, ledger, config, "single")
    assert {p.name for p in created} == {
        "main.beancount",
        "investments.beancount",
        "prices.beancount",
    }
    main = (tmp_path / "main.beancount").read_text()
    assert 'option "operating_currency" "EUR"' in main
    assert 'include "firefly.beancount"' in main
    assert init_ledger_files(tmp_path, ledger, config, "single") == []


def test_main_declares_the_output_language(ledger):
    from firefly_reports import i18n

    def main():
        return render_main_beancount(ledger, parse_ledger_config(None), "single")

    assert 'option "language" "en"' in main()
    i18n.load("it")
    try:
        assert 'option "language" "it"' in main()
    finally:
        i18n.load("en")


def test_main_operating_currency_defaults_to_most_used(ledger):
    text = render_main_beancount(ledger, parse_ledger_config(None), "single")
    assert 'option "operating_currency" "EUR"' in text


def test_dry_run_prints_and_writes_nothing(tmp_path, splits, config, labels, capsys):
    out = tmp_path / "x" / "firefly.beancount"
    run_export(FakeClient(splits), export_request(None, None, out, config, dry_run=True), labels)
    assert "commodity EUR" in capsys.readouterr().out
    assert not out.parent.exists()


def test_run_export_write_failure_is_a_ledger_error(tmp_path, splits, config, labels):
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory\n")
    req = export_request(None, None, blocker, config, layout="single", timestamp=False)
    with pytest.raises(LedgerError) as exc:
        run_export(FakeClient(splits), req, labels)
    assert "Cannot write" in str(exc.value)


def test_empty_export_writes_nothing_and_exits_1(tmp_path, config, labels, capsys):
    out = tmp_path / "ledger"
    out.mkdir()
    accounts = out / "accounts.beancount"
    accounts.write_text("2024-12-31 open Assets:Conto\n")
    year_file = out / "firefly-2024.beancount"
    year_file.write_text('2024-12-31 * "x"\n  Assets:Conto  1 EUR\n')
    req = export_request(None, None, out, config, timestamp=False)
    assert run_export(FakeClient([]), req, labels) == 1
    # existing files are left intact (no header-only accounts.beancount, no orphan years)
    assert accounts.read_text() == "2024-12-31 open Assets:Conto\n"
    assert year_file.read_text() == '2024-12-31 * "x"\n  Assets:Conto  1 EUR\n'
    assert "No transactions found" in capsys.readouterr().err


def test_empty_single_export_keeps_existing_file(tmp_path, config, labels, capsys):
    out = tmp_path / "ledger"
    out.mkdir()
    single = out / "firefly.beancount"
    single.write_text("; keep me\n")
    req = export_request(None, None, out, config, layout="single", timestamp=False)
    assert run_export(FakeClient([]), req, labels) == 1
    assert single.read_text() == "; keep me\n"
    assert "No transactions found" in capsys.readouterr().err


def test_empty_dry_run_prints_nothing_and_exits_1(tmp_path, config, labels, capsys):
    req = export_request(None, None, tmp_path / "out", config, dry_run=True)
    assert run_export(FakeClient([]), req, labels) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No transactions found" in captured.err


def test_run_export_warns_once_per_cross_root_account(tmp_path, labels, capsys):
    cfg = parse_ledger_config(
        {"classify_by": "account", "accounts": {"Bar": "Assets:Bar"}}
    )  # expense mapped under Assets
    splits = [_split("1", "Conto", "Bar"), _split("2", "Conto", "Bar")]
    req = export_request(None, None, tmp_path / "out", cfg, layout="single", timestamp=False)
    assert run_export(FakeClient(splits), req, labels) == 0
    err = capsys.readouterr().err
    assert "Bar" in err and "Assets:Bar" in err and "Expense account" in err
    assert err.count("Assets:Bar") == 1  # once per account, not once per split


def test_validate_without_bean_check_reports_missing(
    tmp_path, splits, config, labels, monkeypatch, capsys
):
    monkeypatch.setattr("shutil.which", lambda name: None)
    req = export_request(None, None, tmp_path, config, layout="single", validate=True)
    assert run_export(FakeClient(splits), req, labels) == 2
    assert "bean-check" in capsys.readouterr().err


def test_run_bean_check_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert run_bean_check(Path("x")).available is False


def test_run_bean_check_failure_is_parsed(tmp_path):
    bad = tmp_path / "bad.beancount"
    bad.write_text('2025-01-01 open Assets:A\n2025-01-02 * "x"\n  Assets:A  1 EUR\n')
    result = run_bean_check(bad)
    if not result.available:
        pytest.skip("bean-check not installed")
    assert not result.ok and result.problems


# ---------- integration with bean-check ----------

needs_bean_check = pytest.mark.skipif(
    shutil.which("bean-check") is None, reason="bean-check not installed"
)


@needs_bean_check
def test_generated_file_passes_bean_check(tmp_path, ledger, labels, config):
    path = tmp_path / "firefly.beancount"
    path.write_text(render(ledger, labels, config), encoding="utf-8")
    proc = subprocess.run(["bean-check", str(path)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@needs_bean_check
def test_full_ledger_with_init_passes_bean_check(tmp_path, splits, config, labels):
    req = export_request(
        None, None, tmp_path, config, layout="single", init=True, validate=True, timestamp=False
    )
    assert run_export(FakeClient(splits), req, labels) == 0
    proc = subprocess.run(
        ["bean-check", str(tmp_path / "main.beancount")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@needs_bean_check
def test_italian_output_passes_bean_check(tmp_path, splits, config):
    try:
        i18n.load("it")
        labels = LedgerLabels.from_i18n()
        out = render(build_ledger(splits, AccountResolver(config, labels)), labels, config)
    finally:
        i18n.load("en")
    path = tmp_path / "firefly.beancount"
    path.write_text(out, encoding="utf-8")
    proc = subprocess.run(["bean-check", str(path)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
