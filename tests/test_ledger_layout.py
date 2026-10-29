"""Yearly layout, orphan detection and the mapping-file scaffold (offline)."""

import json
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from firefly_reports import i18n
from firefly_reports.cli import main as cli_main
from firefly_reports.firefly_client import FireflyClient
from firefly_reports.ledger.accounts import AccountResolver
from firefly_reports.ledger.convert import build_ledger
from firefly_reports.ledger.errors import AccountCollisionError, LedgerError
from firefly_reports.ledger.export import (
    find_orphans,
    plan_files,
    render_main_beancount,
    run_export,
    run_scaffold,
)
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import load_ledger_config, parse_ledger_config
from firefly_reports.ledger.writers import BeancountWriter, WriterOptions
from tests.ledger_helpers import export_request


def main():
    """Run the CLI on sys.argv like the 1.x entry point: a non-zero code exits."""
    code = cli_main()
    if code:
        raise SystemExit(code)


FIXTURE = Path(__file__).parent / "fixtures" / "firefly_transactions.json"
MAP = {
    "classify_by": "account",  # these tests pin the counterpart-account naming rules
    "investment_accounts": {"Acme Investments": "Acme"},
    "commodities": ["EUR", "USD"],
}
needs_bean_check = pytest.mark.skipif(
    shutil.which("bean-check") is None, reason="bean-check not installed"
)


class FakeClient:
    def __init__(self, splits):
        self.splits = splits

    def get_transactions(self, start=None, end=None, tx_type=None):
        return self.splits

    def get_transaction_links(self, resolve_types=True):
        return []


def _split(jid, src, dst, src_type="Asset account", dst_type="Expense account", date="2025-01-01"):
    return {
        "type": "withdrawal",
        "date": date,
        "amount": "10.00",
        "currency_code": "EUR",
        "source_name": src,
        "source_type": src_type,
        "destination_name": dst,
        "destination_type": dst_type,
        "transaction_journal_id": jid,
        "group_id": jid,
        "description": "d",
    }


@pytest.fixture(autouse=True)
def _english():
    yield
    i18n.load("en")


@pytest.fixture
def splits():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return FireflyClient._flatten_transactions(None, payload["data"])  # type: ignore[arg-type]


@pytest.fixture
def labels():
    return LedgerLabels.from_i18n()


@pytest.fixture
def config():
    return parse_ledger_config(MAP)


@pytest.fixture
def ledger(splits, config, labels):
    return build_ledger(splits, AccountResolver(config, labels))


@pytest.fixture
def options(labels, config):
    return WriterOptions(labels=labels, commodities=config.commodities)


def request(out, config, **kw):
    kw.setdefault("timestamp", False)
    return export_request(None, None, out, config, **kw)


# ---------- layout ----------


def test_by_year_is_ordered_and_partitions_the_ledger(ledger):
    years = ledger.by_year()
    assert list(years) == [2024, 2025]
    assert sum(len(y.transactions) for y in years.values()) == len(ledger.transactions)
    assert all(tx.date.year == year for year, y in years.items() for tx in y.transactions)


def test_yearly_plan_has_accounts_plus_one_file_per_year(ledger, options):
    files = plan_files(ledger, "yearly", BeancountWriter(), options)
    assert list(files) == ["accounts.beancount", "firefly-2024.beancount", "firefly-2025.beancount"]


def test_open_and_commodity_only_in_accounts_file(ledger, options):
    files = plan_files(ledger, "yearly", BeancountWriter(), options)
    assert " open " in files["accounts.beancount"]
    assert "commodity EUR" in files["accounts.beancount"]
    assert re.search(r"^\d{4}-\d\d-\d\d \* ", files["accounts.beancount"], re.M) is None
    for name in ("firefly-2024.beancount", "firefly-2025.beancount"):
        assert " open " not in files[name] and " commodity " not in files[name]


def test_year_files_hold_each_transaction_exactly_once(ledger, options):
    writer = BeancountWriter()
    ids = re.compile(r'^  firefly_id: "(\d+)"', re.M)
    single = ids.findall(writer.render(ledger, options))
    per_year = [
        i
        for name, text in plan_files(ledger, "yearly", writer, options).items()
        if name.startswith("firefly-")
        for i in ids.findall(text)
    ]
    assert sorted(per_year, key=int) == sorted(single, key=int)
    assert len(per_year) == len(set(per_year)) == len(ledger.transactions)


def test_single_layout_equals_plain_render(ledger, options):
    writer = BeancountWriter()
    assert plan_files(ledger, "single", writer, options) == {
        "firefly.beancount": writer.render(ledger, options)
    }


def test_yearly_output_is_deterministic_regardless_of_input_order(splits, config, labels, options):
    writer = BeancountWriter()

    def build(data):
        return plan_files(
            build_ledger(data, AccountResolver(config, labels)), "yearly", writer, options
        )

    assert build(splits) == build(list(reversed(splits)))


def test_year_file_columns_depend_only_on_that_year(ledger, options):
    files = plan_files(ledger, "yearly", BeancountWriter(), options)
    text_2024 = files["firefly-2024.beancount"]
    assert "Expenses:" not in text_2024  # only opening balance in 2024
    posting = next(line for line in text_2024.splitlines() if "Equity:Opening-Balances" in line)
    assert posting.startswith("  Equity:Opening-Balances  ")  # no padding for 2025-only names


def test_main_beancount_includes_follow_the_layout(ledger, config):
    yearly = render_main_beancount(ledger, config, "yearly")
    assert 'include "accounts.beancount"' in yearly
    assert 'include "firefly-*.beancount"' in yearly
    single = render_main_beancount(ledger, config, "single")
    assert 'include "firefly.beancount"' in single and "accounts.beancount" not in single


# ---------- run_export, yearly ----------


def test_run_export_yearly_writes_files_and_rerun_is_a_noop(tmp_path, splits, config, labels):
    out = tmp_path / "ledger"
    req = request(out, config, init=True)
    assert run_export(FakeClient(splits), req, labels) == 0
    names = sorted(p.name for p in out.iterdir())
    assert names == [
        "accounts.beancount",
        "firefly-2024.beancount",
        "firefly-2025.beancount",
        "investments.beancount",
        "main.beancount",
        "prices.beancount",
    ]
    before = {p.name: p.stat().st_mtime_ns for p in out.iterdir()}
    assert run_export(FakeClient(splits), req, labels) == 0
    assert {p.name: p.stat().st_mtime_ns for p in out.iterdir()} == before


def test_changed_year_is_the_only_rewritten_file(tmp_path, splits, config, labels):
    out = tmp_path / "ledger"
    run_export(FakeClient(splits), request(out, config), labels)
    mtimes = {p.name: p.stat().st_mtime_ns for p in out.iterdir()}
    changed = [dict(s) for s in splits]
    for s in changed:
        if s["transaction_journal_id"] == "14":  # April 2025 payment
            s["description"] = "Updated installment"
    run_export(FakeClient(changed), request(out, config), labels)
    after = {p.name: p.stat().st_mtime_ns for p in out.iterdir()}
    assert after["firefly-2025.beancount"] != mtimes["firefly-2025.beancount"]
    assert after["firefly-2024.beancount"] == mtimes["firefly-2024.beancount"]
    assert after["accounts.beancount"] == mtimes["accounts.beancount"]


def test_yearly_layout_rejects_date_filters(tmp_path, splits, config, labels):
    from datetime import date

    req = export_request(date(2025, 1, 1), None, tmp_path, config)
    with pytest.raises(LedgerError) as exc:
        run_export(FakeClient(splits), req, labels)
    assert "--layout single" in str(exc.value)


def test_orphans_are_reported_never_deleted(tmp_path, splits, config, labels, capsys):
    out = tmp_path / "ledger"
    out.mkdir()
    (out / "firefly.beancount").write_text("; old single file\n")
    (out / "firefly-2019.beancount").write_text("; stale year\n")
    (out / "notes.txt").write_text("keep\n")
    run_export(FakeClient(splits), request(out, config), labels)
    err = capsys.readouterr().err
    assert "firefly.beancount" in err and "firefly-2019.beancount" in err
    assert "notes.txt" not in err
    assert (out / "firefly.beancount").exists() and (out / "firefly-2019.beancount").exists()


def test_find_orphans_for_missing_directory(tmp_path):
    assert find_orphans(tmp_path / "nope", set(), BeancountWriter()) == []


def test_dry_run_yearly_separates_files(tmp_path, splits, config, labels, capsys):
    run_export(FakeClient(splits), request(tmp_path / "x", config, dry_run=True), labels)
    out = capsys.readouterr().out
    assert "; ===== accounts.beancount =====" in out
    assert "; ===== firefly-2025.beancount =====" in out
    assert not (tmp_path / "x").exists()


def test_dry_run_single_is_pure_ledger(tmp_path, splits, config, labels, capsys):
    run_export(FakeClient(splits), request(tmp_path, config, layout="single", dry_run=True), labels)
    assert "=====" not in capsys.readouterr().out


@needs_bean_check
def test_yearly_layout_with_glob_include_passes_bean_check(tmp_path, splits, config, labels):
    out = tmp_path / "ledger"
    req = request(out, config, init=True, validate=True)
    assert run_export(FakeClient(splits), req, labels) == 0
    proc = subprocess.run(
        ["bean-check", str(out / "main.beancount")], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@needs_bean_check
def test_yearly_dry_run_validate_passes(tmp_path, splits, config, labels):
    req = request(tmp_path, config, dry_run=True, validate=True)
    assert run_export(FakeClient(splits), req, labels) == 0


@needs_bean_check
def test_yearly_italian_passes_bean_check(tmp_path, splits, config):
    i18n.load("it")
    labels = LedgerLabels.from_i18n()
    req = request(tmp_path, parse_ledger_config(MAP), init=True, validate=True)
    assert run_export(FakeClient(splits), req, labels) == 0


# ---------- scaffold ----------


def scaffold(tmp_path, splits, labels, *, map_text=None, dry_run=False):
    map_path = tmp_path / "beancount_map.yaml"
    if map_text is not None:
        map_path.write_text(map_text, encoding="utf-8")
    config = load_ledger_config(map_path if map_path.is_file() else None)
    config = replace(config, classify_by="account")  # these tests pin the account-based draft
    req = export_request(None, None, tmp_path / "ledger", config, dry_run=dry_run)
    code = run_scaffold(FakeClient(splits), req, labels, map_path)
    return code, map_path


def test_scaffold_creates_yaml_and_no_ledger_files(tmp_path, splits, labels, capsys):
    code, map_path = scaffold(tmp_path, splits, labels)
    assert code == 0 and map_path.is_file()
    assert not (tmp_path / "ledger").exists()
    cfg = load_ledger_config(map_path)
    assert cfg.accounts["Checking Account"] == "Assets:Checking-Account"
    assert cfg.accounts["Café Münch & Söhne"] == "Expenses:Cafe-Munch-Sohne"
    assert cfg.operating_currency == ("EUR",) and cfg.commodities == ("EUR", "USD")
    err = capsys.readouterr().err
    assert "Firefly account" in err and "Beancount account" in err


def test_scaffolded_mapping_gives_the_same_ledger_as_no_mapping(tmp_path, splits, labels):
    _, map_path = scaffold(tmp_path, splits, labels)
    writer = BeancountWriter()

    def render(config):
        led = build_ledger(splits, AccountResolver(config, labels))
        return plan_files(led, "yearly", writer, WriterOptions(labels=labels))

    assert render(load_ledger_config(map_path)) == render(
        parse_ledger_config({"classify_by": "account"})
    )


def test_scaffold_lists_only_automatic_accounts(tmp_path, splits, labels):
    _, map_path = scaffold(tmp_path, splits, labels)
    text = map_path.read_text(encoding="utf-8")
    assert "Equity:" not in text and "Assets:Cash" not in text  # special accounts
    assert "(no name)" not in text
    assert "# investment_accounts:" in text and '#   "Checking Account": "Broker"' in text
    assert "# fallback:" in text


def test_scaffold_dry_run_prints_and_writes_nothing(tmp_path, splits, labels, capsys):
    code, map_path = scaffold(tmp_path, splits, labels, dry_run=True)
    assert code == 0 and not map_path.exists()
    assert "accounts:" in capsys.readouterr().out


def test_scaffold_never_modifies_an_existing_mapping(tmp_path, splits, labels, capsys):
    original = 'accounts:\n  "Checking Account": "Assets:Bank"\n'
    code, map_path = scaffold(tmp_path, splits, labels, map_text=original)
    assert code == 0
    assert map_path.read_text() == original
    captured = capsys.readouterr()
    assert "left untouched" in captured.err
    assert '"Checking Account"' not in captured.out  # already mapped
    assert '"Home Mortgage": "Liabilities:Home-Mortgage"' in captured.out  # new account


def test_scaffold_reports_nothing_new_when_mapping_is_complete(tmp_path, splits, labels, capsys):
    scaffold(tmp_path, splits, labels)
    capsys.readouterr()
    scaffold(tmp_path, splits, labels, map_text=(tmp_path / "beancount_map.yaml").read_text())
    captured = capsys.readouterr()
    assert captured.out == "" and "covers everything" in captured.err


def _colliding():
    return [
        _split("1", "Account A", "Bar"),
        _split("2", "Account-A", "Bar", date="2025-01-02"),
    ]


def test_scaffold_comments_out_collisions_and_export_stops_until_resolved(tmp_path, labels, capsys):
    data = _colliding()
    _, map_path = scaffold(tmp_path, data, labels)
    text = map_path.read_text(encoding="utf-8")
    assert '# "Account A": "Assets:Account-A"  # TODO collision' in text
    assert "collision(s)" in capsys.readouterr().err

    config = load_ledger_config(map_path)  # parses fine
    assert "Account A" not in config.accounts
    with pytest.raises(AccountCollisionError):
        build_ledger(data, AccountResolver(config, labels))

    fixed = text.replace('# "Account A": "Assets:Account-A"', '"Account A": "Assets:Account-A-1"')
    map_path.write_text(fixed, encoding="utf-8")
    config = load_ledger_config(map_path)
    ledger = build_ledger(data, AccountResolver(config, labels))
    accounts = {p.account for tx in ledger.transactions for p in tx.postings}
    assert {"Assets:Account-A-1", "Assets:Account-A"} <= accounts


def test_scaffold_leaves_names_shared_by_several_account_types_automatic(tmp_path, labels):
    data = [
        _split("1", "Bank", "Amazon"),
        _split("2", "Amazon", "Bank", src_type="Asset account", dst_type="Expense account"),
    ]
    data[1]["destination_name"] = "Bank"
    _, map_path = scaffold(tmp_path, data, labels)
    text = map_path.read_text(encoding="utf-8")
    assert '# "Bank"  # left automatic' in text
    assert '"Bank":' not in re.sub(r"^\s*#.*$", "", text, flags=re.M)
    config = load_ledger_config(map_path)
    assert "Bank" not in config.accounts


def test_scaffold_quotes_awkward_names(tmp_path, labels):
    data = [_split("1", 'Bank "one": #2', "Bar")]
    _, map_path = scaffold(tmp_path, data, labels)
    assert load_ledger_config(map_path).accounts['Bank "one": #2'] == "Assets:Bank-one-2"


def test_scaffold_is_translated(tmp_path, splits):
    i18n.load("it")
    labels = LedgerLabels.from_i18n()
    _, map_path = scaffold(tmp_path, splits, labels)
    text = map_path.read_text(encoding="utf-8")
    assert "Bozza creata da" in text and "Expenses:Non-Classificato" in text


# ---------- CLI ----------


@pytest.fixture
def cli_env(tmp_path, monkeypatch, splits):
    from unittest import mock

    monkeypatch.chdir(tmp_path)
    for var in ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG"):
        monkeypatch.delenv(var, raising=False)
    with mock.patch("firefly_reports.cli._options.FireflyClient") as cls:
        cls.return_value.get_transactions.return_value = splits
        yield tmp_path


def run_cli(monkeypatch, *args):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "firefly-reports",
            "export",
            "beancount",
            "--url",
            "https://f.test",
            "--token",
            "t",
            *args,
        ],
    )
    main()


def test_cli_scaffold_then_export_two_pass_flow(cli_env, monkeypatch, capsys):
    run_cli(monkeypatch, "--scaffold")
    assert (cli_env / "beancount_map.yaml").is_file()
    assert not (cli_env / "ledger").exists()
    run_cli(monkeypatch, "--no-timestamp", "--init")
    assert (cli_env / "ledger" / "firefly-2025.beancount").is_file()
    assert (cli_env / "ledger" / "main.beancount").is_file()


def test_cli_yearly_with_dates_exits_before_fetching(cli_env, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, "--start", "2025-01-01")
    assert exc.value.code == 1
    assert "--layout single" in capsys.readouterr().err


def test_cli_single_layout_with_dates_still_works(cli_env, monkeypatch):
    run_cli(
        monkeypatch, "--layout", "single", "--start", "2025-01-01", "--out", "o", "--allow-unmapped"
    )
    assert (cli_env / "o" / "firefly.beancount").is_file()


def test_cli_scaffold_with_explicit_missing_map_creates_it(cli_env, monkeypatch):
    run_cli(monkeypatch, "--scaffold", "--map", "custom.yaml")
    assert (cli_env / "custom.yaml").is_file()
