"""The ``report`` command end to end (offline): orchestration and argument validation errors.

All collaborators of ``main()`` (FireflyClient plus every build_* / render_*
function) are patched in the ``firefly_reports.main`` namespace so the tests
run fully offline.
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from unittest import mock

import pytest

from firefly_reports.cli import main as cli_main
from firefly_reports.demo import data as demo_data
from firefly_reports.demo.client import DemoClient

OPTIONS = "firefly_reports.cli._options"
URL = "https://firefly.example.com"
TOKEN = "test-token"
CREDS = ["--url", URL, "--token", TOKEN]
RANGE_ARGS = ["--start", "2025-01-01", "--end", "2025-06-30"]


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    """Isolate cwd and FIREFLY_* env vars so main() sees a clean environment."""
    monkeypatch.chdir(tmp_path)
    for var in ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG", "FIREFLY_LEGACY_REPORT"):
        monkeypatch.delenv(var, raising=False)
    # load_dotenv() searches upward from the package, not from cwd: without this a
    # developer's real .env would repopulate the variables removed above.
    monkeypatch.setattr(f"{OPTIONS}.load_dotenv", lambda *a, **k: None)
    return tmp_path


@dataclass
class Pipeline:
    """The offline collaborators of main(): a DemoClient spy, a render recorder, a workbook mock."""

    client: mock.MagicMock
    rendered: list[tuple[str, str]] = field(default_factory=list)  # (report key, file name)
    fail: set[str] = field(default_factory=set)  # report keys whose PDF render raises
    workbook: mock.MagicMock | None = None

    @property
    def keys(self) -> list[str]:
        return [key for key, _ in self.rendered]


@pytest.fixture
def pipeline(clean_env):
    """Run main() offline: DemoClient behind a spy, PDF renders recorded, workbook mocked."""
    state = Pipeline(client=mock.MagicMock(wraps=DemoClient()))

    def record(spec, data, path, legacy):
        if spec.key in state.fail:
            raise RuntimeError(f"{spec.key} boom")
        state.rendered.append((spec.key, Path(path).name))

    with (
        mock.patch(f"{OPTIONS}.FireflyClient", return_value=state.client),
        mock.patch("firefly_reports.reports.pipeline._render_one", side_effect=record),
        mock.patch("firefly_reports.reports.pipeline.write_workbook") as workbook,
    ):
        state.workbook = workbook
        yield state


def _tx(tx_id):
    """A complete transaction dict (builders read amount, date, names ...)."""
    return {**demo_data.TXN_2025[0], "id": tx_id}


def _run_main(monkeypatch, *args):
    """Run the CLI (current form: the ``report`` subcommand); a non-zero code exits."""
    monkeypatch.setattr(sys, "argv", ["firefly-reports", "report", *args])
    code = cli_main()
    if code:
        raise SystemExit(code)


# ---------------------------------------------------------------------------
# main() — orchestration
# ---------------------------------------------------------------------------


def test_main_range_mode_happy_path(pipeline, clean_env, monkeypatch):
    """Range mode fetches data, builds reports and renders PDF + Excel."""
    out_dir = clean_env / "out"
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--out", str(out_dir))
    pipeline.client.get_transactions.assert_called_once_with(date(2025, 1, 1), date(2025, 6, 30))
    assert "yoy" not in pipeline.keys
    assert pipeline.keys.count("cash_flow") == 1
    assert pipeline.keys.count("summary") == 1
    assert pipeline.keys.count("account_statements") == 1
    assert "tagged" not in pipeline.keys
    pipeline.workbook.assert_called_once()
    assert out_dir.is_dir()


def test_main_year_mode(pipeline, clean_env, monkeypatch):
    """Year mode unlocks YoY, historical and liquidity forecast reports."""
    _run_main(monkeypatch, *CREDS, "--year", "2025", "--out", str(clean_env / "out"))
    client = pipeline.client
    assert client.get_transactions.call_count == 2
    client.get_transactions.assert_any_call(date(2025, 1, 1), date(2025, 12, 31))
    client.get_transactions.assert_any_call(date(2024, 1, 1), date(2024, 12, 31))
    assert client.get_annual_totals.call_count == 3
    for key in ("yoy", "historical_growth", "liquidity_forecast"):
        assert pipeline.keys.count(key) == 1


def test_main_year_mode_custom_historical_years(pipeline, clean_env, monkeypatch):
    """--years 5 fetches five years of historical data."""
    _run_main(
        monkeypatch, *CREDS, "--year", "2025", "--years", "5", "--out", str(clean_env / "out")
    )
    assert pipeline.client.get_annual_totals.call_count == 5


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
    pipeline.client.get_transactions.assert_any_call(date(2025, 4, 1), date(2026, 3, 31))
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
    pipeline.client.get_transactions.assert_any_call(date(2024, 2, 29), date(2025, 2, 28))


def test_main_no_pdf_no_excel(pipeline, clean_env, monkeypatch):
    """--no-pdf/--no-excel skip all rendering but still fetch and process."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--no-pdf", "--no-excel")
    assert pipeline.rendered == []
    pipeline.workbook.assert_not_called()
    pipeline.client.get_transactions.assert_called_once()


def test_main_tags_generate_tagged_report(pipeline, clean_env, monkeypatch):
    """--tags enables the tagged transaction report."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--tags", "tax, business")
    assert ("tagged", "tagged_tax_business_2025-01-01__2025-06-30.pdf") in pipeline.rendered


def test_main_all_tags_report(pipeline, clean_env, monkeypatch):
    """--all-tags builds and renders the comprehensive tags report."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--all-tags")
    assert pipeline.keys.count("all_tags") == 1


def test_main_legacy_report(pipeline, clean_env, monkeypatch):
    """--legacy-report swaps summary/journal for the audit log."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--legacy-report")
    assert pipeline.keys.count("audit_log") == 1
    assert "summary" not in pipeline.keys and "journal" not in pipeline.keys


def test_main_legacy_report_from_env(pipeline, clean_env, monkeypatch):
    """FIREFLY_LEGACY_REPORT=true enables legacy mode without the CLI flag."""
    monkeypatch.setenv("FIREFLY_LEGACY_REPORT", "true")
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    assert "audit_log" in pipeline.keys


def test_main_fetch_links_deep_fetch(pipeline, clean_env, monkeypatch):
    """--fetch-links deep-fetches linked transactions not already downloaded."""
    client = pipeline.client
    client.get_transaction_links.return_value = [{"inward_id": "9", "outward_id": "10"}]
    client.fetch_link_details.return_value = [_tx("9"), _tx("10")]
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--fetch-links")
    client.fetch_link_details.assert_called_once()
    assert "linkage_audit" in pipeline.keys


def test_main_fetch_links_skips_known_ids(pipeline, clean_env, monkeypatch):
    """Linked transactions already in the period are not re-fetched."""
    client = pipeline.client
    client.get_transactions.return_value = [_tx("9")]
    client.get_transaction_links.return_value = [{"inward_id": "9", "outward_id": None}]
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--fetch-links")
    client.fetch_link_details.assert_not_called()


def test_main_linkage_rendered_when_groups_exist(pipeline, clean_env, monkeypatch):
    """The linkage audit PDF is rendered whenever link groups exist."""
    _run_main(monkeypatch, *CREDS, "--year", "2025")
    assert pipeline.keys.count("linkage_audit") == 1


def test_main_linkage_skipped_without_links_or_fetch_links(pipeline, clean_env, monkeypatch):
    pipeline.client.get_transaction_links.return_value = []
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    assert "linkage_audit" not in pipeline.keys


def test_main_global_filters_from_cli(pipeline, clean_env, monkeypatch, capsys):
    """CLI filter flags filter both periods and the per-account fetch."""
    _run_main(
        monkeypatch,
        *CREDS,
        "--year",
        "2025",
        "--accounts-include",
        "1",
        "--categories-exclude",
        "X,Y",
        "--hide-transfers",
        "--reconciled-only",
    )
    assert "global filters:" in capsys.readouterr().out
    pipeline.client.get_account_transactions.assert_called_once_with(
        1, date(2025, 1, 1), date(2025, 12, 31)
    )


def test_main_accounts_exclude_removes_account(pipeline, clean_env, monkeypatch):
    """Excluded accounts get no per-account statement fetch."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--accounts-exclude", "1")
    fetched = [c.args[0] for c in pipeline.client.get_account_transactions.call_args_list]
    assert fetched and 1 not in fetched


def test_main_fetches_related_resources(pipeline, clean_env, monkeypatch, capsys):
    """Budgets, bills and liabilities trigger their per-item fetches."""
    _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    client = pipeline.client
    client.get_liability_transactions.assert_called_once_with(
        30, date(2025, 1, 1), date(2025, 6, 30)
    )
    assert client.get_budget_limits.call_count == len(demo_data.BUDGETS)
    assert client.get_bill_transactions.call_count == len(demo_data.BILLS)
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
    pipeline.fail = {"cash_flow", "account_statements"}
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    assert exc.value.code == 3
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "files failed" in out
    pipeline.workbook.assert_called_once()


def test_main_excel_failure_reported(pipeline, clean_env, monkeypatch, capsys):
    """A failing Excel render is reported in the final summary."""
    pipeline.workbook.side_effect = RuntimeError("xlsx boom")
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    assert exc.value.code == 3
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "Re-run with --debug" in out


def test_main_reraises_fatal_fetch_error(pipeline, clean_env, monkeypatch):
    """A failure while fetching data propagates out of main()."""
    pipeline.client.get_transactions.side_effect = ConnectionError("unreachable")
    with pytest.raises(ConnectionError):
        _run_main(monkeypatch, *CREDS, *RANGE_ARGS)


def test_main_uses_config_file(pipeline, clean_env, monkeypatch, capsys):
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
    with mock.patch(f"{OPTIONS}.FireflyClient", return_value=pipeline.client) as factory:
        _run_main(monkeypatch, *RANGE_ARGS, "--out", str(clean_env / "out"))
    assert factory.call_args.args[:2] == ("https://config.example.com", "config-token")
    assert "tagged" in pipeline.keys and "all_tags" in pipeline.keys
    assert "global filters:" in capsys.readouterr().out


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
    assert "URL is required" in capsys.readouterr().err


def test_main_exits_on_invalid_url(clean_env, monkeypatch, capsys):
    """main() rejects a URL without scheme."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, "--url", "firefly.local", "--token", TOKEN, *RANGE_ARGS)
    assert "invalid Firefly III URL" in capsys.readouterr().err


def test_main_exits_without_token(clean_env, monkeypatch, capsys):
    """main() aborts when no token is available and stdin is not a TTY."""
    monkeypatch.setattr(sys, "stdin", mock.Mock(isatty=lambda: False))
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, "--url", URL, *RANGE_ARGS)
    assert "token is required" in capsys.readouterr().err


def test_main_year_and_start_are_mutually_exclusive(clean_env, monkeypatch, capsys):
    """--year cannot be combined with --start/--end."""
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS, "--year", "2025", "--start", "2025-01-01")
    assert exc.value.code == 1
    assert "use either --year or --start/--end" in capsys.readouterr().err


def test_main_config_year_conflicts_with_start(clean_env, monkeypatch, capsys):
    """A year from the config file also conflicts with --start/--end."""
    (clean_env / "firefly-reports.toml").write_text("year = 2025\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, *RANGE_ARGS)
    assert "use either --year or --start/--end" in capsys.readouterr().err


def test_main_requires_dates_or_year(clean_env, monkeypatch, capsys):
    """Without --year both --start and --end are required."""
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS)
    assert exc.value.code == 1
    assert "provide --year" in capsys.readouterr().err


def test_main_invalid_start_date(clean_env, monkeypatch, capsys):
    """An unparseable --start date aborts."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--start", "2025-13-01", "--end", "2025-12-31")
    assert "invalid date for --start" in capsys.readouterr().err


def test_main_start_after_end_rejected(clean_env, monkeypatch, capsys):
    """--start must not be after --end."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--start", "2025-12-31", "--end", "2025-01-01")
    assert "must not be after" in capsys.readouterr().err


@pytest.mark.parametrize("year", ["1899", "2101"])
def test_main_year_out_of_range(clean_env, monkeypatch, capsys, year):
    """Years outside 1900-2100 are rejected."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--year", year)
    assert "invalid year" in capsys.readouterr().err


def test_main_invalid_fiscal_year_start(clean_env, monkeypatch, capsys):
    """A malformed MM-DD fiscal year start is rejected."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--year", "2025", "--fiscal-year-start", "13-40")
    assert "invalid fiscal year start" in capsys.readouterr().err


def test_main_fiscal_feb29_requires_leap_year(clean_env, monkeypatch, capsys):
    """A 02-29 fiscal start is rejected for a non-leap year."""
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, *CREDS, "--year", "2025", "--fiscal-year-start", "02-29")
    assert "02-29 requires a leap year" in capsys.readouterr().err


def test_main_invalid_year_from_config(clean_env, monkeypatch, capsys):
    """A non-numeric year from the config file is rejected."""
    (clean_env / "firefly-reports.toml").write_text('year = "abc"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS)
    assert exc.value.code == 1
    assert "invalid year 'abc'" in capsys.readouterr().err


def test_main_tagged_render_failure_reported(pipeline, clean_env, monkeypatch, capsys):
    """A failing tagged-report render is reported but does not stop main()."""
    pipeline.fail = {"tagged"}
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, *CREDS, *RANGE_ARGS, "--tags", "tax")
    assert exc.value.code == 3
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "files failed" in out
    pipeline.workbook.assert_called_once()
