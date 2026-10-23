"""Credentials, dates, comma lists and the debug log (CLI option helpers)."""

import getpass
import logging
import sys
from datetime import date
from pathlib import Path
from unittest import mock

import pytest

from firefly_reports.cli._console import setup_debug_log
from firefly_reports.cli._options import csv_list, parse_cli_date, resolve_credentials
from firefly_reports.errors import ConfigurationError
from firefly_reports.reports.options import Period

URL = "https://firefly.example.com"
TOKEN = "test-token"


def _resolve(url, token, config, env=None, prompt=None):
    import os

    return resolve_credentials(
        url, token, config, os.environ if env is None else env, prompt=prompt
    )


def test_resolve_credentials_cli_wins(monkeypatch):
    """CLI args take precedence over env vars and config file values."""
    monkeypatch.setenv("FIREFLY_URL", "https://env.example.com")
    monkeypatch.setenv("FIREFLY_TOKEN", "env-token")
    url, token = _resolve(URL, TOKEN, {"url": "https://cfg.example.com", "token": "cfg"})
    assert (url, token) == (URL, TOKEN)


def test_resolve_credentials_config_beats_env(monkeypatch):
    """Same order as every other setting: the config file wins over the environment."""
    monkeypatch.setenv("FIREFLY_URL", "https://env.example.com")
    monkeypatch.setenv("FIREFLY_TOKEN", "env-token")
    url, token = _resolve(None, None, {"url": "https://cfg.example.com", "token": "cfg"})
    assert (url, token) == ("https://cfg.example.com", "cfg")


def test_resolve_credentials_env_fallback(monkeypatch):
    """Environment variables (and .env) are used when the config file has no value."""
    monkeypatch.setenv("FIREFLY_URL", "https://env.example.com")
    monkeypatch.setenv("FIREFLY_TOKEN", "env-token")
    url, token = _resolve(None, None, {})
    assert (url, token) == ("https://env.example.com", "env-token")


def test_resolve_credentials_config_without_env(monkeypatch):
    """Config file values work when the environment is empty."""
    monkeypatch.delenv("FIREFLY_URL", raising=False)
    monkeypatch.delenv("FIREFLY_TOKEN", raising=False)
    url, token = _resolve(None, None, {"url": URL, "token": "cfg-token"})
    assert (url, token) == (URL, "cfg-token")


def test_resolve_credentials_requires_url(monkeypatch):
    """A missing URL raises a clear ConfigurationError."""
    monkeypatch.delenv("FIREFLY_URL", raising=False)
    with pytest.raises(ConfigurationError, match="URL is required"):
        _resolve(None, TOKEN, {})


def test_resolve_credentials_rejects_invalid_url(monkeypatch):
    """A URL without scheme/netloc is rejected."""
    monkeypatch.delenv("FIREFLY_URL", raising=False)
    with pytest.raises(ConfigurationError, match="invalid Firefly III URL"):
        _resolve("firefly.example.com", TOKEN, {})


def test_resolve_credentials_requires_token_without_prompt(monkeypatch):
    """A missing token raises when no prompt is available (stdin is not a TTY)."""
    monkeypatch.delenv("FIREFLY_TOKEN", raising=False)
    with pytest.raises(ConfigurationError, match="token is required"):
        _resolve(URL, None, {})


def test_resolve_credentials_prompts_for_the_token():
    """With a prompt the token is asked interactively."""
    url, token = _resolve(URL, None, {}, env={}, prompt=lambda question: "prompted-token")
    assert (url, token) == (URL, "prompted-token")


def test_default_prompt_asks_getpass_only_on_a_tty(monkeypatch):
    from firefly_reports.cli._options import default_prompt

    monkeypatch.setattr(sys, "stdin", mock.Mock(isatty=lambda: False))
    assert default_prompt("token: ") is None
    monkeypatch.setattr(sys, "stdin", mock.Mock(isatty=lambda: True))
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "typed")
    assert default_prompt("token: ") == "typed"


def test_parse_cli_date_valid():
    """A well-formed YYYY-MM-DD string is parsed into a date."""
    assert parse_cli_date("2025-02-28", "--start") == date(2025, 2, 28)


def test_parse_cli_date_invalid():
    """A malformed date raises ConfigurationError naming the flag."""
    with pytest.raises(ConfigurationError, match="invalid date for --start"):
        parse_cli_date("28/02/2025", "--start")


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
    assert csv_list(value) == expected


def test_prev_year_dates_plain():
    """Both dates shift back exactly one year."""
    p = Period.between(date(2025, 3, 1), date(2025, 12, 31)).previous
    assert (p.start, p.end) == (date(2024, 3, 1), date(2024, 12, 31))


def test_prev_year_dates_leap_day():
    """Feb 29 falls back to Feb 28 in the previous (non-leap) year."""
    p = Period.between(date(2024, 2, 29), date(2024, 2, 29)).previous
    assert (p.start, p.end) == (date(2023, 2, 28), date(2023, 2, 28))


def testsetup_debug_log_disabled():
    """Without --debug the logger only gets a NullHandler."""
    logger = setup_debug_log(False, Path("unused"))
    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)
    for h in list(logger.handlers):
        logger.removeHandler(h)


def testsetup_debug_log_explicit_file(tmp_path, capsys):
    """With --debug and --debug-file a FileHandler writes to that path."""
    log_file = tmp_path / "debug.log"
    logger = setup_debug_log(True, tmp_path, str(log_file))
    logger.debug("hello")
    assert logger.level == logging.DEBUG
    assert log_file.exists()
    assert "Debug log" in capsys.readouterr().out
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.setLevel(logging.NOTSET)


def testsetup_debug_log_default_file(tmp_path):
    """Without --debug-file the log goes to <out>/debug_<timestamp>.log."""
    logger = setup_debug_log(True, tmp_path)
    assert len(list(tmp_path.glob("debug_*.log"))) == 1
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.setLevel(logging.NOTSET)
