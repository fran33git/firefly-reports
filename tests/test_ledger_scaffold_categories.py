"""First pass: the scaffold proposes category mappings with split counts (offline)."""

import pytest
import yaml

from firefly_reports import i18n
from firefly_reports.ledger.export import ExportRequest, run_export, run_scaffold
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import load_ledger_config, parse_ledger_config
from tests.test_ledger_category_mode import deposit, split, withdrawal


class Client:
    def __init__(self, splits):
        self.splits = splits

    def get_transactions(self, start=None, end=None, tx_type=None):
        return self.splits

    def get_transaction_links(self, resolve_types=True):
        return []


@pytest.fixture
def labels():
    i18n.load("en")
    return LedgerLabels.from_i18n()


SPLITS = [
    withdrawal("1", "Cibo"),
    withdrawal("2", "Cibo"),
    withdrawal("3", "Cibo"),
    withdrawal("4", "Auto"),
    withdrawal("5", None),
    deposit("6", "Fatture"),
    deposit("7", None),
    deposit("8", None),
]


def scaffold(tmp_path, labels, splits=SPLITS, mode="category", existing=None, **sections):
    map_path = tmp_path / "m.yaml"
    if existing is not None:
        map_path.write_text(existing, encoding="utf-8")
    config = parse_ledger_config(
        yaml.safe_load(existing) if existing else {"classify_by": mode, **sections}
    )
    req = ExportRequest(None, None, tmp_path / "out", config, allow_unmapped=True)
    rc = run_scaffold(Client(splits), req, labels, map_path)
    return rc, map_path


def test_new_scaffold_lists_categories_with_counts_sorted(tmp_path, labels):
    rc, path = scaffold(tmp_path, labels)
    text = path.read_text(encoding="utf-8")
    assert rc == 0 and "classify_by: category" in text
    cats = text[text.index("categories:") :]
    assert cats.index('"Cibo"') < cats.index('"Auto"')  # 3 splits before 1
    assert '"Cibo": "Expenses:Cibo"  # split: 3' in cats
    assert '"Fatture": "Income:Fatture"  # split: 1' in cats
    assert cats.index("expense:") < cats.index('"Cibo"') < cats.index("income:")


def test_new_scaffold_round_trips_through_the_loader(tmp_path, labels):
    _, path = scaffold(tmp_path, labels)
    cfg = parse_ledger_config(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert cfg.classify_by == "category"
    assert cfg.categories_expense == {"Cibo": "Expenses:Cibo", "Auto": "Expenses:Auto"}
    assert cfg.categories_income == {"Fatture": "Income:Fatture"}


def test_scaffold_lists_uncategorized_counts_as_comment(tmp_path, labels):
    _, path = scaffold(tmp_path, labels)
    text = path.read_text(encoding="utf-8")
    assert "# expense: 1" in text and "# income: 2" in text


def test_scaffold_in_category_mode_omits_counterpart_accounts(tmp_path, labels):
    _, path = scaffold(tmp_path, labels)
    text = path.read_text(encoding="utf-8")
    assert "Bar Sport" not in text and "Cliente" not in text
    assert "Conto" in text  # the real account is still listed


def test_account_mode_scaffold_has_no_categories_but_records_the_mode(tmp_path, labels):
    _, path = scaffold(tmp_path, labels, mode="account")
    text = path.read_text(encoding="utf-8")
    assert "categories:" not in text and "classify_by: account" in text
    assert "Bar Sport" in text
    assert load_ledger_config(path).classify_by == "account"


def test_account_mode_scaffold_then_export_without_flag_is_not_blocked(tmp_path, labels):
    _, path = scaffold(tmp_path, labels, mode="account")
    config = load_ledger_config(path)
    request = ExportRequest(None, None, tmp_path / "out", config, map_path=path, timestamp=False)
    assert run_export(Client(SPLITS), request, labels) == 0


def test_existing_mapping_prints_only_unmapped_categories(tmp_path, labels, capsys):
    existing = (
        'classify_by: category\naccounts:\n  "Conto": "Assets:Conto"\n'
        'categories:\n  expense:\n    "Cibo": "Expenses:Cibo"\n'
    )
    rc, path = scaffold(tmp_path, labels, existing=existing)
    out = capsys.readouterr()
    assert rc == 0 and path.read_text(encoding="utf-8") == existing  # never touched
    assert '"Auto": "Expenses:Auto"  # split: 1' in out.out
    assert '"Fatture": "Income:Fatture"' in out.out and '"Cibo"' not in out.out
    assert "categories:" not in out.out  # section exists: only the blocks to merge
    assert "Cibo" in out.err  # the on-screen summary lists every category


def test_existing_mapping_without_categories_section_prints_whole_section(tmp_path, labels, capsys):
    existing = 'classify_by: category\naccounts:\n  "Conto": "Assets:Conto"\n'
    scaffold(tmp_path, labels, existing=existing)
    out = capsys.readouterr().out
    assert out.startswith("categories:\n  expense:\n")
    assert '"Cibo": "Expenses:Cibo"' in out


def test_nothing_new_prints_nothing_to_stdout(tmp_path, labels, capsys):
    existing = (
        'classify_by: category\naccounts:\n  "Conto": "Assets:Conto"\n'
        'categories:\n  expense:\n    "Cibo": "Expenses:Cibo"\n    "Auto": "Expenses:Auto"\n'
        '  income:\n    "Fatture": "Income:Fatture"\n'
    )
    scaffold(tmp_path, labels, existing=existing)
    out = capsys.readouterr()
    assert out.out == ""


def test_colliding_auto_categories_are_flagged_in_the_draft(tmp_path, labels):
    splits = [withdrawal("1", "A b"), withdrawal("2", "A-b")]
    _, path = scaffold(tmp_path, labels, splits)
    text = path.read_text(encoding="utf-8")
    assert text.count("TODO") >= 1


def test_transfer_categories_are_not_listed(tmp_path, labels):
    sp = split("1", "transfer", "Conto", "Asset account", "Risparmio", "Asset account",
               category_name="Giroconti")  # fmt: skip
    _, path = scaffold(tmp_path, labels, [sp])
    assert "Giroconti" not in path.read_text(encoding="utf-8")
