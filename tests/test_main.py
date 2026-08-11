"""Unit tests for main.py (CLI entry point).

All collaborators of ``main()`` (FireflyClient plus every build_* / render_*
function) are patched in the ``firefly_reports.main`` namespace so the tests
run fully offline.
"""

import argparse
import getpass
import logging
import stat
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pytest

from firefly_reports.main import (
    _csv_list,
    _parse_cli_date,
    _prev_year_dates,
    _resolve_credentials,
    _setup_debug_log,
    cmd_init,
    main,
    parse_args,
)

MAIN = "firefly_reports.main"
URL = "https://firefly.example.com"
TOKEN = "test-token"
CREDS = ["--url", URL, "--token", TOKEN]
RANGE_ARGS = ["--start", "2025-01-01", "--end", "2025-06-30"]

BUILD_FUNCS = [
    "apply_global_filters",
    "build_account_statements",
    "build_all_tags_report",
    "build_audit_log",
    "build_bills_report",
    "build_budget_vs_actual",
    "build_cash_flow",
    "build_category_ledger",
    "build_cumulative_cashflow",
    "build_expense_trend",
    "build_historical_report",
    "build_income_concentration",
    "build_income_expense",
    "build_journal",
    "build_kpi_scorecard",
    "build_liabilities_report",
    "build_linkage_report",
    "build_liquidity_forecast",
    "build_net_worth",
    "build_payee_ledger",
    "build_performance_forecast",
    "build_savings_goals",
    "build_summary",
    "build_tagged_report",
    "build_tax_summary",
    "build_transaction_register",
    "build_yoy_comparison",
]

RENDER_FUNCS = [
    "render_account_statements_pdf",
    "render_all_tags_pdf",
    "render_audit_log_pdf",
    "render_bills_pdf",
    "render_budget_vs_actual_pdf",
    "render_cash_flow_pdf",
    "render_category_ledger_pdf",
    "render_cumulative_cashflow_pdf",
    "render_expense_trend_pdf",
    "render_forecast_pdf",
    "render_historical_report_pdf",
    "render_income_concentration_pdf",
    "render_income_expense_dashboard_pdf",
    "render_income_expense_pdf",
    "render_journal_pdf",
    "render_kpi_scorecard_pdf",
    "render_kpi_trend_dashboard_pdf",
    "render_liabilities_pdf",
    "render_linkage_audit_pdf",
    "render_liquidity_forecast_pdf",
    "render_net_worth_pdf",
    "render_payee_ledger_pdf",
    "render_savings_goals_pdf",
    "render_summary_pdf",
    "render_tagged_report_pdf",
    "render_tax_summary_pdf",
    "render_transaction_register_pdf",
    "render_yoy_pdf",
]


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    """Isolate cwd and FIREFLY_* env vars so main() sees a clean environment."""
    monkeypatch.chdir(tmp_path)
    for var in ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG", "FIREFLY_LEGACY_REPORT"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


@pytest.fixture
def pipeline(clean_env):
    """Patch every external collaborator of main() with sensible fake data."""
    names = [*BUILD_FUNCS, *RENDER_FUNCS, "render_all_xlsx_full", "FireflyClient"]
    with mock.patch.multiple(MAIN, **{name: mock.DEFAULT for name in names}) as mocks:
        client = mocks["FireflyClient"].return_value
        client.get_transactions.return_value = []
        client.get_asset_accounts.return_value = [
            {"id": "1", "attributes": {"name": "Main", "current_balance": "1000.00"}}
        ]
        client.get_liability_accounts.return_value = []
        client.get_account_transactions.return_value = []
        client.get_liability_transactions.return_value = []
        client.get_budgets.return_value = []
        client.get_bills.return_value = []
        client.get_piggy_banks.return_value = []
        client.get_about.return_value = {"version": "6.2.10"}
        client.get_about_user.return_value = {"email": "user@example.com"}
        client.get_transaction_links.return_value = []
        client.fetch_link_details.return_value = []
        client.get_annual_totals.return_value = {
            "income": Decimal("1200.00"),
            "expense": Decimal("800.00"),
        }
        client.get_top_categories_for_year.return_value = []

        mocks["build_cash_flow"].return_value = {
            "total_in": Decimal("1200.00"),
            "total_out": Decimal("800.00"),
            "net": Decimal("400.00"),
        }
        mocks["build_income_expense"].return_value = {}
        mocks["build_transaction_register"].return_value = {"total_transactions": 0}
        mocks["build_kpi_scorecard"].return_value = {
            "avg_monthly_in": Decimal("1200.00"),
            "avg_monthly_out": Decimal("800.00"),
            "savings_rate": 33,
            "cash_runway": 6,
            "hhi": 0,
            "monthly_trend": [],
        }
        mocks["build_linkage_report"].return_value = {"groups": []}
        yield mocks


def _run_main(monkeypatch, *args):
    """Invoke main() with the given CLI arguments."""
    monkeypatch.setattr(sys, "argv", ["firefly-reports", *args])
    main()


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


def test_parse_args_init_subcommand(monkeypatch):
    """The 'init' subcommand is parsed into args.command."""
    monkeypatch.setattr(sys, "argv", ["firefly-reports", "init"])
    args = parse_args()
    assert args.command == "init"


def test_parse_args_defaults(monkeypatch):
    """All optional flags default to None/False/empty when omitted."""
    monkeypatch.setattr(sys, "argv", ["firefly-reports", *RANGE_ARGS])
    args = parse_args()
    assert args.command is None
    assert args.url is None
    assert args.token is None
    assert args.year is None
    assert args.owner is None
    assert args.currency is None
    assert args.out is None
    assert args.lang is None
    assert args.years is None
    assert args.tags == ""
    assert args.link_delay is None
    assert args.accounts_include is None
    assert args.accounts_exclude is None
    assert args.categories_include is None
    assert args.categories_exclude is None
    assert args.fiscal_year_start is None
    assert args.debug_file is None
    for flag in (
        "legacy_report",
        "fetch_links",
        "all_tags",
        "no_pdf",
        "no_excel",
        "hide_transfers",
        "reconciled_only",
        "debug",
    ):
        assert getattr(args, flag) is False


def test_parse_args_all_flags(monkeypatch):
    """Every CLI flag is parsed into the expected attribute and type."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "firefly-reports",
            "--url",
            URL,
            "--token",
            "t",
            "--year",
            "2025",
            "--owner",
            "Me",
            "--currency",
            "$",
            "--out",
            "./out",
            "--lang",
            "it",
            "--years",
            "5",
            "--legacy-report",
            "--tags",
            "a,b",
            "--fetch-links",
            "--link-delay",
            "0.5",
            "--all-tags",
            "--no-pdf",
            "--no-excel",
            "--accounts-include",
            "1,2",
            "--accounts-exclude",
            "3",
            "--categories-include",
            "A",
            "--categories-exclude",
            "B",
            "--hide-transfers",
            "--reconciled-only",
            "--fiscal-year-start",
            "04-01",
            "--debug",
            "--debug-file",
            "x.log",
        ],
    )
    args = parse_args()
    assert args.url == URL
    assert args.year == 2025
    assert args.lang == "it"
    assert args.years == 5
    assert args.link_delay == 0.5
    assert args.accounts_include == "1,2"
    assert args.accounts_exclude == "3"
    assert args.categories_include == "A"
    assert args.categories_exclude == "B"
    assert args.fiscal_year_start == "04-01"
    assert args.debug_file == "x.log"
    for flag in (
        "legacy_report",
        "fetch_links",
        "all_tags",
        "no_pdf",
        "no_excel",
        "hide_transfers",
        "reconciled_only",
        "debug",
    ):
        assert getattr(args, flag) is True


@pytest.mark.parametrize(
    "bad",
    [
        ["--lang", "fr"],
        ["--years", "4"],
        ["--year", "abc"],
        ["--link-delay", "fast"],
    ],
    ids=["bad-lang", "bad-years", "bad-year", "bad-link-delay"],
)
def test_parse_args_rejects_invalid_values(monkeypatch, bad):
    """argparse exits with an error on invalid choices or types."""
    monkeypatch.setattr(sys, "argv", ["firefly-reports", *bad])
    with pytest.raises(SystemExit):
        parse_args()


# ---------------------------------------------------------------------------
# _resolve_credentials
# ---------------------------------------------------------------------------


def test_resolve_credentials_cli_wins(monkeypatch):
    """CLI args take precedence over env vars and config file values."""
    monkeypatch.setenv("FIREFLY_URL", "https://env.example.com")
    monkeypatch.setenv("FIREFLY_TOKEN", "env-token")
    args = argparse.Namespace(url=URL, token=TOKEN)
    url, token = _resolve_credentials(args, {"url": "https://cfg.example.com", "token": "cfg"})
    assert (url, token) == (URL, TOKEN)


def test_resolve_credentials_env_fallback(monkeypatch):
    """Env vars are used when CLI args are absent."""
    monkeypatch.setenv("FIREFLY_URL", "https://env.example.com")
    monkeypatch.setenv("FIREFLY_TOKEN", "env-token")
    args = argparse.Namespace(url=None, token=None)
    url, token = _resolve_credentials(args, {"url": "https://cfg.example.com", "token": "cfg"})
    assert (url, token) == ("https://env.example.com", "env-token")


def test_resolve_credentials_config_fallback(monkeypatch):
    """Config file values are the last non-interactive fallback."""
    monkeypatch.delenv("FIREFLY_URL", raising=False)
    monkeypatch.delenv("FIREFLY_TOKEN", raising=False)
    args = argparse.Namespace(url=None, token=None)
    url, token = _resolve_credentials(args, {"url": URL, "token": "cfg-token"})
    assert (url, token) == (URL, "cfg-token")


def test_resolve_credentials_exits_without_url(monkeypatch, capsys):
    """A missing URL aborts with exit code 1 and a clear message."""
    monkeypatch.delenv("FIREFLY_URL", raising=False)
    args = argparse.Namespace(url=None, token=TOKEN)
    with pytest.raises(SystemExit) as exc:
        _resolve_credentials(args, {})
    assert exc.value.code == 1
    assert "URL is required" in capsys.readouterr().out


def test_resolve_credentials_exits_on_invalid_url(monkeypatch, capsys):
    """A URL without scheme/netloc is rejected."""
    monkeypatch.delenv("FIREFLY_URL", raising=False)
    args = argparse.Namespace(url="firefly.example.com", token=TOKEN)
    with pytest.raises(SystemExit) as exc:
        _resolve_credentials(args, {})
    assert exc.value.code == 1
    assert "invalid Firefly III URL" in capsys.readouterr().out


def test_resolve_credentials_exits_without_token_non_tty(monkeypatch, capsys):
    """A missing token aborts when stdin is not a TTY."""
    monkeypatch.delenv("FIREFLY_TOKEN", raising=False)
    monkeypatch.setattr(sys, "stdin", mock.Mock(isatty=lambda: False))
    args = argparse.Namespace(url=URL, token=None)
    with pytest.raises(SystemExit) as exc:
        _resolve_credentials(args, {})
    assert exc.value.code == 1
    assert "token is required" in capsys.readouterr().out


def test_resolve_credentials_prompts_for_token_on_tty(monkeypatch):
    """On a TTY the token is asked interactively via getpass."""
    monkeypatch.delenv("FIREFLY_TOKEN", raising=False)
    monkeypatch.setattr(sys, "stdin", mock.Mock(isatty=lambda: True))
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "prompted-token")
    args = argparse.Namespace(url=URL, token=None)
    url, token = _resolve_credentials(args, {})
    assert (url, token) == (URL, "prompted-token")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def test_parse_cli_date_valid():
    """A well-formed YYYY-MM-DD string is parsed into a date."""
    assert _parse_cli_date("2025-02-28", "--start") == date(2025, 2, 28)


def test_parse_cli_date_invalid(capsys):
    """A malformed date aborts with exit code 1."""
    with pytest.raises(SystemExit) as exc:
        _parse_cli_date("28/02/2025", "--start")
    assert exc.value.code == 1
    assert "invalid date for --start" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),
        ("", []),
        ("a", ["a"]),
        (" a, b ,,c ", ["a", "b", "c"]),
    ],
)
def test_csv_list(value, expected):
    """Comma-separated options are split and stripped; blanks are dropped."""
    assert _csv_list(value) == expected


def test_prev_year_dates_plain():
    """Both dates shift back exactly one year."""
    start, end = _prev_year_dates(date(2025, 3, 1), date(2025, 12, 31))
    assert (start, end) == (date(2024, 3, 1), date(2024, 12, 31))


def test_prev_year_dates_leap_day():
    """Feb 29 falls back to Feb 28 in the previous (non-leap) year."""
    start, end = _prev_year_dates(date(2024, 2, 29), date(2024, 2, 29))
    assert (start, end) == (date(2023, 2, 28), date(2023, 2, 28))


def test_setup_debug_log_disabled():
    """Without --debug the logger only gets a NullHandler."""
    logger = _setup_debug_log(False, Path("unused"))
    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)
    for h in list(logger.handlers):
        logger.removeHandler(h)


def test_setup_debug_log_explicit_file(tmp_path, capsys):
    """With --debug and --debug-file a FileHandler writes to that path."""
    log_file = tmp_path / "debug.log"
    logger = _setup_debug_log(True, tmp_path, str(log_file))
    logger.debug("hello")
    assert logger.level == logging.DEBUG
    assert log_file.exists()
    assert "Debug log" in capsys.readouterr().out
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.setLevel(logging.NOTSET)


def test_setup_debug_log_default_file(tmp_path):
    """Without --debug-file the log goes to <out>/debug_<timestamp>.log."""
    logger = _setup_debug_log(True, tmp_path)
    assert len(list(tmp_path.glob("debug_*.log"))) == 1
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.setLevel(logging.NOTSET)


# ---------------------------------------------------------------------------
# cmd_init
# ---------------------------------------------------------------------------


def _mock_wizard(monkeypatch, inputs, token=""):
    """Feed scripted answers to input() and a fixed token to getpass."""
    answers = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": token)


def test_cmd_init_aborts_when_user_declines_overwrite(tmp_path, monkeypatch, capsys):
    """An existing config is kept when the user does not answer 'y'."""
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "firefly-reports.toml"
    cfg.write_text("old = true\n", encoding="utf-8")
    _mock_wizard(monkeypatch, ["n"])
    cmd_init()
    assert cfg.read_text(encoding="utf-8") == "old = true\n"
    assert "Aborted" in capsys.readouterr().out


def test_cmd_init_happy_path_with_token(tmp_path, monkeypatch, capsys):
    """Answers are written to the TOML file with owner-only permissions."""
    monkeypatch.chdir(tmp_path)
    _mock_wizard(
        monkeypatch,
        ["", "Mario Rossi", "", "IT", "y", "", "tax, business"],
        token="secret",
    )
    cmd_init()
    cfg = tmp_path / "firefly-reports.toml"
    content = cfg.read_text(encoding="utf-8")
    assert 'url      = "https://firefly.example.com"' in content
    assert 'token    = "secret"' in content
    assert 'owner    = "Mario Rossi"' in content
    assert 'currency = "€"' in content
    assert 'lang     = "it"' in content
    assert "legacy_report = true" in content
    assert 'out      = "./output"' in content
    assert 'tags     = ["tax", "business"]' in content
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600
    # No .gitignore present -> the token warning must be shown.
    assert "WARNING" in capsys.readouterr().out


def test_cmd_init_defaults_without_token(tmp_path, monkeypatch):
    """Blank answers fall back to defaults; the token line stays commented."""
    monkeypatch.chdir(tmp_path)
    _mock_wizard(monkeypatch, ["", "", "", "", "", "", ""])
    cmd_init()
    content = (tmp_path / "firefly-reports.toml").read_text(encoding="utf-8")
    assert 'url      = "https://firefly.example.com"' in content
    assert '# token = ""' in content
    assert 'token    = "' not in content
    assert 'owner    = ""' in content
    assert 'lang     = "en"' in content
    assert "legacy_report = false" in content
    assert "tags     = []" in content


def test_cmd_init_invalid_lang_falls_back_to_en(tmp_path, monkeypatch):
    """An unsupported language answer is coerced to 'en'."""
    monkeypatch.chdir(tmp_path)
    _mock_wizard(monkeypatch, ["", "", "", "fr", "", "", ""])
    cmd_init()
    content = (tmp_path / "firefly-reports.toml").read_text(encoding="utf-8")
    assert 'lang     = "en"' in content


def test_cmd_init_overwrite_accepted(tmp_path, monkeypatch):
    """Answering 'y' rewrites an existing config file."""
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "firefly-reports.toml"
    cfg.write_text("old = true\n", encoding="utf-8")
    _mock_wizard(monkeypatch, ["y", "", "", "", "", "", "", ""])
    cmd_init()
    content = cfg.read_text(encoding="utf-8")
    assert "old = true" not in content
    assert 'url      = "https://firefly.example.com"' in content


def test_cmd_init_no_warning_when_gitignore_covers_config(tmp_path, monkeypatch, capsys):
    """No .gitignore warning is printed when the config file is already ignored."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("firefly-reports.toml\n", encoding="utf-8")
    _mock_wizard(monkeypatch, ["", "", "", "", "", "", ""], token="secret")
    cmd_init()
    assert "WARNING" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main() — orchestration
# ---------------------------------------------------------------------------


def test_main_init_subcommand(clean_env, monkeypatch):
    """'firefly-reports init' dispatches to cmd_init and returns early."""
    with mock.patch(f"{MAIN}.cmd_init") as mock_init:
        _run_main(monkeypatch, "init")
    mock_init.assert_called_once()


def test_main_range_mode_happy_path(pipeline, clean_env, monkeypatch):
    """Range mode fetches data, builds reports and renders PDF + Excel."""
    out_dir = clean_env / "out"
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--out", str(out_dir))
    client = pipeline["FireflyClient"].return_value
    client.get_transactions.assert_called_once_with(date(2025, 1, 1), date(2025, 6, 30))
    pipeline["build_yoy_comparison"].assert_not_called()
    pipeline["render_yoy_pdf"].assert_not_called()
    pipeline["render_cash_flow_pdf"].assert_called_once()
    pipeline["render_summary_pdf"].assert_called_once()
    pipeline["render_account_statements_pdf"].assert_called_once()
    pipeline["render_tagged_report_pdf"].assert_not_called()
    pipeline["render_all_xlsx_full"].assert_called_once()
    assert out_dir.is_dir()


def test_main_year_mode(pipeline, clean_env, monkeypatch):
    """Year mode unlocks YoY, historical and liquidity forecast reports."""
    _run_main(monkeypatch, *CREDS, "--year", "2025", "--out", str(clean_env / "out"))
    client = pipeline["FireflyClient"].return_value
    assert client.get_transactions.call_count == 2
    client.get_transactions.assert_any_call(date(2025, 1, 1), date(2025, 12, 31))
    client.get_transactions.assert_any_call(date(2024, 1, 1), date(2024, 12, 31))
    pipeline["build_yoy_comparison"].assert_called_once()
    assert client.get_annual_totals.call_count == 3
    pipeline["render_yoy_pdf"].assert_called_once()
    pipeline["render_historical_report_pdf"].assert_called_once()
    pipeline["render_liquidity_forecast_pdf"].assert_called_once()


def test_main_year_mode_custom_historical_years(pipeline, clean_env, monkeypatch):
    """--years 5 fetches five years of historical data."""
    _run_main(
        monkeypatch, *CREDS, "--year", "2025", "--years", "5", "--out", str(clean_env / "out")
    )
    client = pipeline["FireflyClient"].return_value
    assert client.get_annual_totals.call_count == 5


def test_main_year_mode_fiscal_year_start(pipeline, clean_env, monkeypatch, capsys):
    """A custom fiscal year start shifts the reporting period."""
    _run_main(
        monkeypatch,
        *CREDS,
        "--year",
        "2025",
        "--fiscal-year-start",
        "04-01",
        "--out",
        str(clean_env / "out"),
    )
    client = pipeline["FireflyClient"].return_value
    client.get_transactions.assert_any_call(date(2025, 4, 1), date(2026, 3, 31))
    assert "Fiscal year" in capsys.readouterr().out


def test_main_year_mode_leap_fiscal_year(pipeline, clean_env, monkeypatch):
    """A 02-29 fiscal start in a leap year ends on 02-28 of the next year."""
    _run_main(
        monkeypatch,
        *CREDS,
        "--year",
        "2024",
        "--fiscal-year-start",
        "02-29",
        "--out",
        str(clean_env / "out"),
    )
    client = pipeline["FireflyClient"].return_value
    client.get_transactions.assert_any_call(date(2024, 2, 29), date(2025, 2, 28))


def test_main_no_pdf_no_excel(pipeline, clean_env, monkeypatch):
    """--no-pdf/--no-excel skip all rendering but still fetch and process."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--no-pdf", "--no-excel")
    for name in RENDER_FUNCS:
        pipeline[name].assert_not_called()
    pipeline["render_all_xlsx_full"].assert_not_called()
    pipeline["build_cash_flow"].assert_called_once()


def test_main_tags_generate_tagged_report(pipeline, clean_env, monkeypatch):
    """--tags enables the tagged transaction report."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--tags", "tax, business")
    assert pipeline["build_tagged_report"].call_args.args[1] == ["tax", "business"]
    pipeline["render_tagged_report_pdf"].assert_called_once()


def test_main_all_tags_report(pipeline, clean_env, monkeypatch):
    """--all-tags builds and renders the comprehensive tags report."""
    pipeline["build_all_tags_report"].return_value = {"tags": []}
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--all-tags")
    pipeline["build_all_tags_report"].assert_called_once()
    pipeline["render_all_tags_pdf"].assert_called_once()


def test_main_legacy_report(pipeline, clean_env, monkeypatch):
    """--legacy-report swaps summary/journal for the audit log."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--legacy-report")
    pipeline["build_audit_log"].assert_called_once()
    pipeline["render_audit_log_pdf"].assert_called_once()
    pipeline["render_summary_pdf"].assert_not_called()
    pipeline["render_journal_pdf"].assert_not_called()


def test_main_legacy_report_from_env(pipeline, clean_env, monkeypatch):
    """FIREFLY_LEGACY_REPORT=true enables legacy mode without the CLI flag."""
    monkeypatch.setenv("FIREFLY_LEGACY_REPORT", "true")
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    pipeline["build_audit_log"].assert_called_once()


def test_main_fetch_links_deep_fetch(pipeline, clean_env, monkeypatch):
    """--fetch-links deep-fetches linked transactions not already downloaded."""
    client = pipeline["FireflyClient"].return_value
    client.get_transaction_links.return_value = [{"inward_id": "9", "outward_id": "10"}]
    client.fetch_link_details.return_value = [{"id": "9"}, {"id": "10"}]
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--fetch-links")
    client.fetch_link_details.assert_called_once()
    pipeline["render_linkage_audit_pdf"].assert_called_once()


def test_main_fetch_links_skips_known_ids(pipeline, clean_env, monkeypatch):
    """Linked transactions already in the period are not re-fetched."""
    client = pipeline["FireflyClient"].return_value
    client.get_transactions.return_value = [{"id": "9"}]
    client.get_transaction_links.return_value = [{"inward_id": "9", "outward_id": None}]
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--fetch-links")
    client.fetch_link_details.assert_not_called()


def test_main_linkage_rendered_when_groups_exist(pipeline, clean_env, monkeypatch):
    """The linkage audit PDF is rendered whenever link groups exist."""
    pipeline["build_linkage_report"].return_value = {"groups": [{"id": 1}]}
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    pipeline["render_linkage_audit_pdf"].assert_called_once()


def test_main_global_filters_from_cli(pipeline, clean_env, monkeypatch):
    """CLI filter flags trigger apply_global_filters on both periods."""
    _run_main(
        monkeypatch,
        *CREDS,
        *RANGE_ARGS,
        "--accounts-include",
        "1",
        "--categories-exclude",
        "X,Y",
        "--hide-transfers",
        "--reconciled-only",
    )
    assert pipeline["apply_global_filters"].call_count == 2
    client = pipeline["FireflyClient"].return_value
    client.get_account_transactions.assert_called_once_with(1, date(2025, 1, 1), date(2025, 6, 30))


def test_main_accounts_exclude_removes_account(pipeline, clean_env, monkeypatch):
    """Excluded accounts get no per-account statement fetch."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--accounts-exclude", "1")
    client = pipeline["FireflyClient"].return_value
    client.get_account_transactions.assert_not_called()


def test_main_fetches_related_resources(pipeline, clean_env, monkeypatch, capsys):
    """Budgets, bills and liabilities trigger their per-item fetches."""
    client = pipeline["FireflyClient"].return_value
    client.get_liability_accounts.return_value = [{"id": "30", "attributes": {}}]
    client.get_budgets.return_value = [{"id": "101"}]
    client.get_bills.return_value = [{"id": "201"}]
    client.get_piggy_banks.return_value = [{"id": "301"}]
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    client.get_liability_transactions.assert_called_once_with(
        30, date(2025, 1, 1), date(2025, 6, 30)
    )
    client.get_budget_limits.assert_called_once_with("101", date(2025, 1, 1), date(2025, 6, 30))
    client.get_bill_transactions.assert_called_once_with("201", date(2025, 1, 1), date(2025, 6, 30))
    assert "liabilities" in capsys.readouterr().out


def test_main_debug_log_file(pipeline, clean_env, monkeypatch):
    """--debug --debug-file creates the requested log file."""
    log_file = clean_env / "debug.log"
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--debug", "--debug-file", str(log_file))
    assert log_file.exists()
    logger = logging.getLogger("firefly_reports")
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.setLevel(logging.NOTSET)


def test_main_continues_after_render_failure(pipeline, clean_env, monkeypatch, capsys):
    """A failing PDF render is reported but does not stop the pipeline."""
    pipeline["render_cash_flow_pdf"].side_effect = RuntimeError("boom")
    pipeline["render_account_statements_pdf"].side_effect = RuntimeError("boom2")
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "files failed" in out
    pipeline["render_all_xlsx_full"].assert_called_once()


def test_main_excel_failure_reported(pipeline, clean_env, monkeypatch, capsys):
    """A failing Excel render is reported in the final summary."""
    pipeline["render_all_xlsx_full"].side_effect = RuntimeError("xlsx boom")
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "Re-run with --debug" in out


def test_main_reraises_fatal_fetch_error(pipeline, clean_env, monkeypatch):
    """A failure while fetching data propagates out of main()."""
    client = pipeline["FireflyClient"].return_value
    client.get_transactions.side_effect = ConnectionError("unreachable")
    with pytest.raises(ConnectionError):
        _run_main(monkeypatch, *CREDS, *RANGE_ARGS)


def test_main_uses_config_file(pipeline, clean_env, monkeypatch):
    """Config file supplies credentials, tags and report options."""
    (clean_env / "firefly-reports.toml").write_text(
        'url = "https://config.example.com"\n'
        'token = "config-token"\n'
        'owner = "Config Owner"\n'
        'tags = ["tax"]\n'
        "[reports]\n"
        "all_tags_report = true\n"
        "[filters]\n"
        "show_transfers = false\n",
        encoding="utf-8",
    )
    _run_main(monkeypatch, *RANGE_ARGS, "--out", str(clean_env / "out"))
    call = pipeline["FireflyClient"].call_args
    assert call.args[:2] == ("https://config.example.com", "config-token")
    pipeline["render_tagged_report_pdf"].assert_called_once()
    pipeline["render_all_tags_pdf"].assert_called_once()
    assert pipeline["apply_global_filters"].call_count == 2


def test_main_exits_on_malformed_config(clean_env, monkeypatch, capsys):
    """A malformed firefly-reports.toml aborts with exit code 1."""
    (clean_env / "firefly-reports.toml").write_text("not = = valid\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch)
    assert exc.value.code == 1
    assert "malformed" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main() — argument validation errors
# ---------------------------------------------------------------------------


def test_main_exits_without_url(clean_env, monkeypatch, capsys):
    """main() aborts when no URL is available from any source."""
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, "--token", TOKEN, *RANGE_ARGS)
    assert exc.value.code == 1
    assert "URL is required" in capsys.readouterr().out


def test_main_exits_on_invalid_url(clean_env, monkeypatch, capsys):
    """main() rejects a URL without scheme."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, "--url", "firefly.local", "--token", TOKEN, *RANGE_ARGS)
    assert "invalid Firefly III URL" in capsys.readouterr().out


def test_main_exits_without_token(clean_env, monkeypatch, capsys):
    """main() aborts when no token is available and stdin is not a TTY."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(isatty=lambda: False))
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, "--url", URL, *RANGE_ARGS)
    assert "token is required" in capsys.readouterr().out


def test_main_year_and_start_are_mutually_exclusive(clean_env, monkeypatch, capsys):
    """--year cannot be combined with --start/--end."""
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS, "--year", "2025", "--start", "2025-01-01")
    assert exc.value.code == 1
    assert "use either --year or --start/--end" in capsys.readouterr().out


def test_main_config_year_conflicts_with_start(clean_env, monkeypatch, capsys):
    """A year from the config file also conflicts with --start/--end."""
    (clean_env / "firefly-reports.toml").write_text("year = 2025\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    assert "use either --year or --start/--end" in capsys.readouterr().out


def test_main_requires_dates_or_year(clean_env, monkeypatch, capsys):
    """Without --year both --start and --end are required."""
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS)
    assert exc.value.code == 1
    assert "provide --year" in capsys.readouterr().out


def test_main_invalid_start_date(clean_env, monkeypatch, capsys):
    """An unparseable --start date aborts."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--start", "2025-13-01", "--end", "2025-12-31")
    assert "invalid date for --start" in capsys.readouterr().out


def test_main_start_after_end_rejected(clean_env, monkeypatch, capsys):
    """--start must not be after --end."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--start", "2025-12-31", "--end", "2025-01-01")
    assert "must not be after" in capsys.readouterr().out


@pytest.mark.parametrize("year", ["1899", "2101"])
def test_main_year_out_of_range(clean_env, monkeypatch, capsys, year):
    """Years outside 1900-2100 are rejected."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--year", year)
    assert "invalid year" in capsys.readouterr().out


def test_main_invalid_fiscal_year_start(clean_env, monkeypatch, capsys):
    """A malformed MM-DD fiscal year start is rejected."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--year", "2025", "--fiscal-year-start", "13-40")
    assert "invalid fiscal year start" in capsys.readouterr().out


def test_main_fiscal_feb29_requires_leap_year(clean_env, monkeypatch, capsys):
    """A 02-29 fiscal start is rejected for a non-leap year."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--year", "2025", "--fiscal-year-start", "02-29")
    assert "02-29 requires a leap year" in capsys.readouterr().out


def test_main_invalid_year_from_config(clean_env, monkeypatch, capsys):
    """A non-numeric year from the config file is rejected."""
    (clean_env / "firefly-reports.toml").write_text('year = "abc"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS)
    assert exc.value.code == 1
    assert "invalid year 'abc'" in capsys.readouterr().out


def test_main_tagged_render_failure_reported(pipeline, clean_env, monkeypatch, capsys):
    """A failing tagged-report render is reported but does not stop main()."""
    pipeline["render_tagged_report_pdf"].side_effect = RuntimeError("tagged boom")
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--tags", "tax")
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "files failed" in out
    pipeline["render_all_xlsx_full"].assert_called_once()
