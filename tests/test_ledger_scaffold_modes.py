"""``--scaffold --append`` and ``--scaffold --overwrite`` on an existing mapping (offline)."""

import sys

import pytest
import yaml

from firefly_reports import i18n
from firefly_reports.cli import main as cli_main
from firefly_reports.ledger import export as export_module
from firefly_reports.ledger.errors import LedgerError
from firefly_reports.ledger.export import (
    SCAFFOLD_APPEND,
    SCAFFOLD_OVERWRITE,
    ExportRequest,
    run_export,
    run_scaffold,
)
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import load_ledger_config, parse_ledger_config
from tests.test_ledger_category_mode import deposit, withdrawal
from tests.test_ledger_mapfile import in_order


def main():
    """Run the CLI on sys.argv like the 1.x entry point: a non-zero code exits."""
    code = cli_main()
    if code:
        raise SystemExit(code)


SPLITS = [withdrawal("1", "Food"), withdrawal("2", "Auto"), deposit("3", "Invoices")]
EXISTING = (
    "# my mapping\n"
    "classify_by: category\n"
    "accounts:\n"
    '  "Bank": "Assets:Bank"  # keep me\n'
    "categories:\n"
    "  expense:\n"
    '    "Food": "Expenses:Food"  # mine\n'
)


class Client:
    def __init__(self, splits=SPLITS):
        self.splits = splits

    def get_transactions(self, start=None, end=None, tx_type=None):
        return self.splits

    def get_transaction_links(self, resolve_types=True):
        return []


@pytest.fixture
def labels():
    i18n.load("en")
    return LedgerLabels.from_i18n()


def scaffold(tmp_path, labels, text=EXISTING, mode=None, confirm=None, **req):
    path = tmp_path / "m.yaml"
    if text is not None:
        path.write_text(text, encoding="utf-8", newline="")
    config = parse_ledger_config(yaml.safe_load(text) if text else {"classify_by": "category"})
    request = ExportRequest(None, None, tmp_path / "out", config, allow_unmapped=True, **req)
    kwargs = {"confirm": confirm}
    if mode:
        kwargs["mode"] = mode
    return run_scaffold(Client(), request, labels, path, **kwargs), path


def siblings(path):
    return sorted(p.name for p in path.parent.iterdir() if p.name.startswith(path.name))


# ---------- --append ----------


def test_append_adds_missing_and_preserves_existing_lines(tmp_path, labels):
    rc, path = scaffold(tmp_path, labels, mode=SCAFFOLD_APPEND)
    new = path.read_text(encoding="utf-8")
    assert rc == 0 and in_order(EXISTING, new)
    cfg = parse_ledger_config(yaml.safe_load(new))
    assert cfg.categories_expense == {"Food": "Expenses:Food", "Auto": "Expenses:Auto"}
    assert cfg.categories_income == {"Invoices": "Income:Invoices"}
    assert cfg.accounts["Bank"] == "Assets:Bank"


def test_append_creates_backup(tmp_path, labels):
    _, path = scaffold(tmp_path, labels, mode=SCAFFOLD_APPEND)
    assert (tmp_path / "m.yaml.bak").read_text(encoding="utf-8") == EXISTING


def test_append_unsafe_file_prints_snippet_and_writes_nothing(tmp_path, labels, capsys):
    flow = 'classify_by: category\ncategories: {expense: {"Food": "Expenses:Food"}}\n'
    rc, path = scaffold(tmp_path, labels, text=flow, mode=SCAFFOLD_APPEND)
    out = capsys.readouterr()
    assert rc == 0 and path.read_text(encoding="utf-8") == flow
    assert siblings(path) == ["m.yaml"]  # no backup either
    assert '"Auto": "Expenses:Auto"' in out.out  # the snippet is printed instead


def test_append_whose_verification_fails_writes_nothing(tmp_path, labels, monkeypatch, capsys):
    monkeypatch.setattr(
        export_module, "append_entries", lambda text, **kw: "classify_by: category\n"
    )
    rc, path = scaffold(tmp_path, labels, mode=SCAFFOLD_APPEND)
    assert rc == 0 and path.read_text(encoding="utf-8") == EXISTING
    assert siblings(path) == ["m.yaml"]
    assert '"Auto"' in capsys.readouterr().out


def test_append_that_loses_a_new_entry_writes_nothing(tmp_path, labels, monkeypatch, capsys):
    real = export_module.append_entries

    def drops_new(text, **kw):
        return real(text, accounts=kw["accounts"], expense=[], income=kw["income"])

    monkeypatch.setattr(export_module, "append_entries", drops_new)
    rc, path = scaffold(tmp_path, labels, mode=SCAFFOLD_APPEND)
    assert rc == 0 and path.read_text(encoding="utf-8") == EXISTING
    assert siblings(path) == ["m.yaml"]
    assert '"Auto"' in capsys.readouterr().out


def test_append_nothing_new_writes_nothing(tmp_path, labels):
    full = EXISTING + '    "Auto": "Expenses:Auto"\n  income:\n    "Invoices": "Income:Invoices"\n'
    rc, path = scaffold(tmp_path, labels, text=full, mode=SCAFFOLD_APPEND)
    assert rc == 0 and path.read_text(encoding="utf-8") == full
    assert siblings(path) == ["m.yaml"]


def test_append_dry_run_writes_nothing_not_even_backup(tmp_path, labels, capsys):
    rc, path = scaffold(tmp_path, labels, mode=SCAFFOLD_APPEND, dry_run=True)
    assert rc == 0 and path.read_text(encoding="utf-8") == EXISTING
    assert siblings(path) == ["m.yaml"]
    assert '"Auto": "Expenses:Auto"' in capsys.readouterr().out


def test_append_preserves_crlf_files(tmp_path, labels):
    crlf = EXISTING.replace("\n", "\r\n")
    _, path = scaffold(tmp_path, labels, text=crlf, mode=SCAFFOLD_APPEND)
    raw = path.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")


def test_append_without_a_file_creates_it_like_a_normal_scaffold(tmp_path, labels):
    rc, path = scaffold(tmp_path, labels, text=None, mode=SCAFFOLD_APPEND)
    assert rc == 0 and "categories:" in path.read_text(encoding="utf-8")


def test_after_append_the_export_passes_the_safety_block(tmp_path, labels):
    _, path = scaffold(tmp_path, labels, mode=SCAFFOLD_APPEND)
    request = ExportRequest(
        None, None, tmp_path / "out", load_ledger_config(path), map_path=path, timestamp=False
    )
    assert run_export(Client(), request, labels) == 0


# ---------- --overwrite ----------


def test_overwrite_declined_keeps_file_and_exits_1(tmp_path, labels):
    rc, path = scaffold(tmp_path, labels, mode=SCAFFOLD_OVERWRITE, confirm=lambda p: False)
    assert rc == 1 and path.read_text(encoding="utf-8") == EXISTING
    assert siblings(path) == ["m.yaml"]


def test_overwrite_without_a_confirm_callback_refuses(tmp_path, labels):
    rc, path = scaffold(tmp_path, labels, mode=SCAFFOLD_OVERWRITE)
    assert rc == 1 and path.read_text(encoding="utf-8") == EXISTING


def test_overwrite_confirmed_makes_timestamped_backup_then_replaces(tmp_path, labels):
    asked = []
    rc, path = scaffold(
        tmp_path, labels, mode=SCAFFOLD_OVERWRITE, confirm=lambda p: asked.append(p) or True
    )
    new = path.read_text(encoding="utf-8")
    assert rc == 0 and asked == [path]
    assert "my mapping" not in new and '"Food": "Expenses:Food"' in new
    (backup,) = [p for p in tmp_path.iterdir() if p.name.startswith("m.yaml.bak-")]
    assert backup.read_text(encoding="utf-8") == EXISTING


def test_overwrite_never_overwrites_an_earlier_backup(tmp_path, labels):
    for _ in range(2):
        scaffold(tmp_path, labels, mode=SCAFFOLD_OVERWRITE, confirm=lambda p: True)
    assert len([p for p in tmp_path.iterdir() if p.name.startswith("m.yaml.bak-")]) == 2


def test_overwrite_backup_failure_does_not_replace(tmp_path, labels, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(export_module.shutil, "copy2", boom)
    with pytest.raises(LedgerError):
        scaffold(tmp_path, labels, mode=SCAFFOLD_OVERWRITE, confirm=lambda p: True)
    assert (tmp_path / "m.yaml").read_text(encoding="utf-8") == EXISTING


def test_overwrite_dry_run_neither_asks_nor_writes(tmp_path, labels, capsys):
    rc, path = scaffold(
        tmp_path, labels, mode=SCAFFOLD_OVERWRITE, dry_run=True,
        confirm=lambda p: pytest.fail("must not ask"),
    )  # fmt: skip
    assert rc == 0 and path.read_text(encoding="utf-8") == EXISTING
    assert siblings(path) == ["m.yaml"]
    assert "classify_by: category" in capsys.readouterr().out


def test_cli_overwrite_regenerates_from_scratch_ignoring_the_old_mapping(cli, monkeypatch):
    path = cli / "beancount_map.yaml"
    path.write_text(
        "classify_by: category\naccounts:\n  Bank: 'Assets:Bank:Main'\n"
        "categories:\n  expense:\n    Food: 'Expenses:Vitto'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("firefly_reports.cli.export._stdin_is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "beancount_map.yaml")
    run_cli(monkeypatch, "--scaffold", "--overwrite")
    cfg = load_ledger_config(path)
    assert cfg.categories_expense["Food"] == "Expenses:Food"  # not the user's old value
    assert "Bank" not in cfg.accounts or cfg.accounts["Bank"] != "Assets:Bank:Bank"


def test_cli_overwrite_can_repair_an_invalid_mapping(cli, monkeypatch):
    path = cli / "beancount_map.yaml"
    path.write_text("accounts:\n  Bank: 'notanaccount'\n", encoding="utf-8")
    monkeypatch.setattr("firefly_reports.cli.export._stdin_is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "beancount_map.yaml")
    run_cli(monkeypatch, "--scaffold", "--overwrite")
    assert load_ledger_config(path).classify_by == "category"


def test_overwrite_without_a_file_creates_it_without_asking(tmp_path, labels):
    rc, path = scaffold(
        tmp_path, labels, text=None, mode=SCAFFOLD_OVERWRITE, confirm=lambda p: pytest.fail("no")
    )
    assert rc == 0 and path.exists()


# ---------- command line ----------


@pytest.fixture
def cli(tmp_path, monkeypatch):
    from unittest import mock

    monkeypatch.chdir(tmp_path)
    for var in ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("firefly_reports.cli._options.load_dotenv", lambda *a, **k: None)
    with mock.patch("firefly_reports.cli._options.FireflyClient") as cls:
        cls.return_value.get_transactions.return_value = SPLITS
        cls.return_value.get_transaction_links.return_value = []
        yield tmp_path


def run_cli(monkeypatch, *args):
    argv = ["firefly-reports", "export", "beancount", "--url", "https://f.test", "--token", "t"]
    monkeypatch.setattr(sys, "argv", [*argv, *args])
    main()


@pytest.mark.parametrize(
    "flags", [["--append"], ["--overwrite"], ["--scaffold", "--append", "--overwrite"]]
)
def test_flags_require_scaffold_and_are_exclusive(cli, monkeypatch, capsys, flags):
    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, *flags)
    assert exc.value.code == 1
    assert "--scaffold" in capsys.readouterr().err


def test_cli_overwrite_non_interactive_refuses(cli, monkeypatch):
    path = cli / "beancount_map.yaml"
    path.write_text(EXISTING, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, "--scaffold", "--overwrite")
    assert exc.value.code == 1 and path.read_text(encoding="utf-8") == EXISTING
    assert sorted(p.name for p in cli.iterdir()) == ["beancount_map.yaml"]


def test_cli_overwrite_confirmed_by_typing_the_file_name(cli, monkeypatch):
    path = cli / "beancount_map.yaml"
    path.write_text(EXISTING, encoding="utf-8")
    monkeypatch.setattr("firefly_reports.cli.export._stdin_is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "beancount_map.yaml")
    run_cli(monkeypatch, "--scaffold", "--overwrite")
    assert "my mapping" not in path.read_text(encoding="utf-8")


def test_cli_overwrite_wrong_word_is_a_refusal(cli, monkeypatch):
    path = cli / "beancount_map.yaml"
    path.write_text(EXISTING, encoding="utf-8")
    monkeypatch.setattr("firefly_reports.cli.export._stdin_is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, "--scaffold", "--overwrite")
    assert exc.value.code == 1 and path.read_text(encoding="utf-8") == EXISTING


def test_cli_append_end_to_end(cli, monkeypatch):
    path = cli / "beancount_map.yaml"
    path.write_text(EXISTING, encoding="utf-8")
    run_cli(monkeypatch, "--scaffold", "--append")
    assert '"Invoices": "Income:Invoices"' in path.read_text(encoding="utf-8")
    assert (cli / "beancount_map.yaml.bak").exists()
