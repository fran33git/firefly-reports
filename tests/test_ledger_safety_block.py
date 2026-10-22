"""The export refuses to run without an up-to-date mapping unless told otherwise (offline)."""

from pathlib import Path

import pytest

from firefly_reports import i18n
from firefly_reports.ledger.errors import LedgerError
from firefly_reports.ledger.export import ExportRequest, run_export, run_scaffold
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import parse_ledger_config
from tests.test_ledger_category_mode import deposit, withdrawal

MAP_PATH = Path("beancount_map.yaml")


class Client:
    def __init__(self, splits):
        self.splits = splits
        self.fetches = 0

    def get_transactions(self, start=None, end=None, tx_type=None):
        self.fetches += 1
        return self.splits

    def get_transaction_links(self, resolve_types=True):
        return []


@pytest.fixture
def labels():
    i18n.load("en")
    return LedgerLabels.from_i18n()


def config(mode="category", **sections):
    return parse_ledger_config({"classify_by": mode, **sections})


def request(tmp_path, cfg, **kw):
    kw.setdefault("map_path", MAP_PATH)
    kw.setdefault("timestamp", False)
    return ExportRequest(None, None, tmp_path / "out", cfg, **kw)


SPLITS = [withdrawal("1", "Cibo"), withdrawal("2", "Nuova"), deposit("3", "Fatture")]
FULL_MAP = {
    "categories": {
        "expense": {"Cibo": "Expenses:Cibo", "Nuova": "Expenses:Nuova"},
        "income": {"Fatture": "Income:Fatture"},
    }
}


def test_export_without_map_file_blocks_before_fetching(labels, tmp_path):
    client = Client(SPLITS)
    with pytest.raises(LedgerError) as exc:
        run_export(client, request(tmp_path, config(), map_path=None), labels)
    assert exc.value.message_key == "ledger.err_map_missing"
    assert client.fetches == 0
    assert not (tmp_path / "out").exists()


def test_missing_map_blocks_in_account_mode_too(labels, tmp_path):
    with pytest.raises(LedgerError) as exc:
        run_export(Client(SPLITS), request(tmp_path, config("account"), map_path=None), labels)
    assert exc.value.message_key == "ledger.err_map_missing"


def test_missing_map_message_points_to_scaffold(labels, tmp_path):
    with pytest.raises(LedgerError) as exc:
        run_export(Client(SPLITS), request(tmp_path, config(), map_path=None), labels)
    assert "--scaffold" in str(exc.value)


def test_unmapped_category_blocks_and_lists_it(labels, tmp_path):
    cfg = config(categories={"expense": {"Cibo": "Expenses:Cibo"}})
    with pytest.raises(LedgerError) as exc:
        run_export(Client(SPLITS), request(tmp_path, cfg), labels)
    assert exc.value.message_key == "ledger.err_unmapped_categories"
    text = str(exc.value)
    assert "Nuova" in text and "Fatture" in text and "Cibo" not in text
    assert "--scaffold --append" in text and "--allow-unmapped" in text
    assert not (tmp_path / "out").exists()


def test_allow_unmapped_proceeds_with_one_warning_per_category(labels, tmp_path, capsys):
    cfg = config(categories={"expense": {"Cibo": "Expenses:Cibo"}})
    assert run_export(Client(SPLITS), request(tmp_path, cfg, allow_unmapped=True), labels) == 0
    err = capsys.readouterr().err
    assert err.count("is not in the mapping file") == 2  # one per missing category
    assert "'Nuova'" in err and "'Fatture'" in err and "'Cibo'" not in err
    assert (tmp_path / "out" / "firefly-2025.beancount").exists()


def test_allow_unmapped_without_a_map_file_uses_automatic_names(labels, tmp_path):
    req = request(tmp_path, config(), map_path=None, allow_unmapped=True)
    assert run_export(Client(SPLITS), req, labels) == 0
    text = (tmp_path / "out" / "firefly-2025.beancount").read_text()
    assert "Expenses:Cibo" in text and "Income:Fatture" in text


def test_category_in_file_with_proposed_value_counts_as_seen(labels, tmp_path):
    cfg = config(**FULL_MAP)
    assert run_export(Client(SPLITS), request(tmp_path, cfg), labels) == 0


def test_mapped_only_on_expense_lane_blocks_for_income(labels, tmp_path):
    splits = [withdrawal("1", "Rimborsi"), deposit("2", "Rimborsi")]
    cfg = config(categories={"expense": {"Rimborsi": "Expenses:Rimborsi"}})
    with pytest.raises(LedgerError) as exc:
        run_export(Client(splits), request(tmp_path, cfg), labels)
    assert "income" in str(exc.value).lower() and "expense: 'Rimborsi'" not in str(exc.value)


def test_unused_key_warns_but_passes(labels, tmp_path, capsys):
    mapping = {"categories": {"expense": {**FULL_MAP["categories"]["expense"], "Vecchia": "Expenses:V"},
                              "income": FULL_MAP["categories"]["income"]}}  # fmt: skip
    assert run_export(Client(SPLITS), request(tmp_path, config(**mapping)), labels) == 0
    assert "Vecchia" in capsys.readouterr().err


def test_uncategorized_never_blocks(labels, tmp_path):
    splits = [withdrawal("1", None), deposit("2", None)]
    assert run_export(Client(splits), request(tmp_path, config(categories={})), labels) == 0


def test_dry_run_is_blocked_too(labels, tmp_path):
    cfg = config(categories={"expense": {"Cibo": "Expenses:Cibo"}})
    with pytest.raises(LedgerError):
        run_export(Client(SPLITS), request(tmp_path, cfg, dry_run=True), labels)


def test_account_mode_missing_categories_do_not_block(labels, tmp_path):
    assert run_export(Client(SPLITS), request(tmp_path, config("account")), labels) == 0


def test_scaffold_is_never_blocked(labels, tmp_path):
    req = request(tmp_path, config(), map_path=None, dry_run=True)
    assert run_scaffold(Client(SPLITS), req, labels, tmp_path / "m.yaml") == 0
