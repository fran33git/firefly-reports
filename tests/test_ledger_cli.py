"""CLI-level tests for ``firefly-reports export beancount`` (fully offline)."""

import json
import sys
from datetime import date
from pathlib import Path
from unittest import mock

import pytest
import requests

from firefly_reports import i18n
from firefly_reports.firefly_client import FireflyClient
from firefly_reports.main import main, parse_args

FIXTURE = Path(__file__).parent / "fixtures" / "firefly_transactions.json"
CREDS = ["--url", "https://firefly.example.com", "--token", "tok"]


@pytest.fixture
def splits():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return FireflyClient._flatten_transactions(None, payload["data"])  # type: ignore[arg-type]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for var in ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG"):
        monkeypatch.delenv(var, raising=False)
    # a developer's real .env must not repopulate the variables removed above
    monkeypatch.setattr("firefly_reports.main.load_dotenv", lambda *a, **k: None)
    yield tmp_path
    i18n.load("en")


@pytest.fixture
def client(splits):
    with mock.patch("firefly_reports.main.FireflyClient") as cls:
        cls.return_value.get_transactions.return_value = splits
        yield cls.return_value


def run(monkeypatch, *args):
    if args[:1] == ("export",):
        # These tests export without a mapping on purpose; the block has its own tests.
        args = (*args, "--allow-unmapped")
    monkeypatch.setattr(sys, "argv", ["firefly-reports", *args])
    main()


def test_parse_args_export(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["firefly-reports", "export", "beancount", "--start", "2025-01-01", "--dry-run"],
    )
    args = parse_args()
    assert (args.command, args.format, args.start, args.dry_run) == (
        "export",
        "beancount",
        "2025-01-01",
        True,
    )
    assert args.map is None and not args.validate and not args.init_files


def test_parse_args_export_keeps_options_given_before_subcommand(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["firefly-reports", "--lang", "it", "--url", "u", "export", "beancount"]
    )
    args = parse_args()
    assert args.lang == "it" and args.url == "u"


def test_parse_args_export_rejects_unknown_format(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["firefly-reports", "export", "hledger"])
    with pytest.raises(SystemExit):
        parse_args()


def test_export_writes_whole_history_by_default(env, client, monkeypatch, capsys):
    run(monkeypatch, "export", "beancount", *CREDS, "--no-timestamp")
    out = env / "ledger"
    assert sorted(p.name for p in out.iterdir()) == [
        "accounts.beancount",
        "firefly-2024.beancount",
        "firefly-2025.beancount",
    ]
    assert "GENERATED - DO NOT EDIT BY HAND" in (out / "accounts.beancount").read_text()
    client.get_transactions.assert_called_once_with(None, None, tx_type="all")
    assert "Wrote 12 transactions in 3 file(s)" in capsys.readouterr().out


def test_export_passes_date_range(env, client, monkeypatch):
    run(
        monkeypatch,
        "export",
        "beancount",
        *CREDS,
        "--start",
        "2025-01-01",
        "--end",
        "2025-03-31",
        "--layout",
        "single",
        "--dry-run",
    )
    client.get_transactions.assert_called_once_with(
        date(2025, 1, 1), date(2025, 3, 31), tx_type="all"
    )


def test_export_dry_run_prints_to_stdout_only(env, client, monkeypatch, capsys):
    run(monkeypatch, "export", "beancount", *CREDS, "--dry-run", "--no-timestamp")
    assert "2025-01-15 * " in capsys.readouterr().out
    assert not (env / "ledger").exists()


def test_export_uses_map_and_lang(env, client, monkeypatch):
    (env / "m.yaml").write_text(
        "classify_by: account\naccounts:\n  'Conto Corrente': 'Assets:Banca:Corrente'\n"
    )
    run(
        monkeypatch,
        "--lang",
        "it",
        "export",
        "beancount",
        *CREDS,
        "--map",
        "m.yaml",
        "--out",
        "out",
    )
    text = (env / "out" / "accounts.beancount").read_text() + (
        env / "out" / "firefly-2025.beancount"
    ).read_text()
    assert "GENERATO - NON MODIFICARE A MANO" in text
    assert "Assets:Banca:Corrente" in text and "categoria:" in text


def test_export_picks_up_default_map_in_cwd(env, client, monkeypatch):
    (env / "beancount_map.yaml").write_text("accounts:\n  'Conto Corrente': 'Assets:Banca'\n")
    run(monkeypatch, "export", "beancount", *CREDS, "--out", "out")
    assert "Assets:Banca" in (env / "out" / "accounts.beancount").read_text()


def test_export_init_flag_creates_main(env, client, monkeypatch):
    run(monkeypatch, "export", "beancount", *CREDS, "--init")
    assert (env / "ledger" / "main.beancount").exists()


def test_export_missing_map_file_exits_1(env, client, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "export", "beancount", *CREDS, "--map", "nope.yaml")
    assert exc.value.code == 1
    assert "nope.yaml" in capsys.readouterr().err


def test_export_invalid_map_exits_1_with_translated_message(env, client, monkeypatch, capsys):
    (env / "m.yaml").write_text("bogus: 1\n")
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "export", "beancount", *CREDS, "--map", "m.yaml")
    assert exc.value.code == 1
    assert "Unknown key 'bogus'" in capsys.readouterr().err


def test_export_collision_exits_1_and_writes_nothing(env, client, monkeypatch, capsys):
    client.get_transactions.return_value = [
        {
            "type": "withdrawal", "date": "2025-01-01", "amount": "1.00", "currency_code": "EUR",
            "source_name": "Conto A", "source_type": "Asset account",
            "destination_name": "Conto-A", "destination_type": "Asset account",
            "transaction_journal_id": "1", "group_id": "1",
        }
    ]  # fmt: skip
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "export", "beancount", *CREDS, "--out", "out")
    assert exc.value.code == 1
    assert "collision" in capsys.readouterr().err
    assert not (env / "out").exists()


def test_export_bad_date_order_exits_1(env, client, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run(
            monkeypatch,
            "export",
            "beancount",
            *CREDS,
            "--start",
            "2025-02-01",
            "--end",
            "2025-01-01",
        )
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "--start (2025-02-01) must not be after --end (2025-01-01)" in captured.err
    assert captured.out == ""  # errors go to stderr, like the other CLI errors


def test_export_without_mapping_exits_1_and_points_to_scaffold(env, client, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["firefly-reports", "export", "beancount", *CREDS])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "--scaffold" in capsys.readouterr().err
    client.get_transactions.assert_not_called()
    assert not (env / "ledger").exists()


def test_export_http_error_exits_1(env, client, monkeypatch, capsys):
    client.get_transactions.side_effect = requests.ConnectionError("down")
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "export", "beancount", *CREDS)
    assert exc.value.code == 1
    assert "down" in capsys.readouterr().err


def test_export_link_fetch_error_exits_1_and_writes_nothing(env, client, monkeypatch, capsys):
    client.get_transaction_links.side_effect = requests.ConnectionError("links down")
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "export", "beancount", *CREDS)
    assert exc.value.code == 1
    assert "links down" in capsys.readouterr().err
    assert not (env / "ledger").exists()


def test_export_scaffold_map_is_directory_exits_1(env, client, monkeypatch, capsys):
    (env / "dir").mkdir()
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "export", "beancount", *CREDS, "--scaffold", "--map", "dir")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Cannot write" in err and "dir" in err


def test_export_non_utf8_map_exits_1(env, client, monkeypatch, capsys):
    (env / "m.yaml").write_bytes(b"\xff\xfe\x00m")
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "export", "beancount", *CREDS, "--map", "m.yaml")
    assert exc.value.code == 1
    assert "Cannot read mapping file" in capsys.readouterr().err


def test_export_validate_ok_with_bean_check(env, client, monkeypatch, capsys):
    import shutil

    if shutil.which("bean-check") is None:
        pytest.skip("bean-check not installed")
    run(monkeypatch, "export", "beancount", *CREDS, "--validate", "--out", "out")
    assert "bean-check: no errors" in capsys.readouterr().err


def test_export_requires_credentials(env, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    with pytest.raises(SystemExit):
        run(monkeypatch, "export", "beancount", "--dry-run")
