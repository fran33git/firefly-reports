"""--trust-insecure-ssl: command line only, reaches the client, notices and errors on stderr."""

import pytest

from firefly_reports import i18n
from firefly_reports.api import connect
from firefly_reports.cli import build_parser, main
from firefly_reports.cli._console import print_trust_notice
from firefly_reports.demo.client import DemoClient
from firefly_reports.errors import UntrustedChainError
from firefly_reports.firefly_client import TrustNotice
from tests.golden.harness import run_main

CREDS = ["--url", "https://demo.invalid", "--token", "x"]
REPORT = ["report", *CREDS, "--year", "2025", "--no-pdf", "--no-excel"]


@pytest.fixture
def made(monkeypatch, tmp_path):
    """Every FireflyClient the CLI builds, recorded as its keyword arguments."""
    calls: list[dict] = []

    def factory(*args, **kwargs):
        calls.append(kwargs)
        return DemoClient()

    monkeypatch.setattr("firefly_reports.cli._options.FireflyClient", factory)
    monkeypatch.setattr("firefly_reports.cli._options.load_dotenv", lambda *a, **k: None)
    for var in ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG", "FIREFLY_TRUST_INSECURE_SSL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    return calls


def test_flag_is_accepted_before_and_after_the_subcommand(made):
    assert main(["--trust-insecure-ssl", *REPORT]) == 0
    assert main([*REPORT, "--trust-insecure-ssl"]) == 0
    assert [c["trust_insecure_ssl"] for c in made] == [True, True]


def test_default_is_off(made):
    assert main(REPORT) == 0
    assert made[-1]["trust_insecure_ssl"] is False


def test_export_passes_the_flag_to_the_client(made, monkeypatch):
    def fake_run(args, client_factory, parse_date, config):
        client_factory()
        return 0

    monkeypatch.setattr("firefly_reports.cli.run_export_command", fake_run)
    assert main(["export", "beancount", *CREDS, "--trust-insecure-ssl"]) == 0
    assert made[-1]["trust_insecure_ssl"] is True


def test_parser_has_the_flag_only_where_a_server_is_contacted(capsys):
    parser = build_parser()
    assert parser.parse_args(["--trust-insecure-ssl", "report"]).trust_insecure_ssl is True
    assert parser.parse_args(["report", "--trust-insecure-ssl"]).trust_insecure_ssl is True
    assert parser.parse_args(["export", "beancount", "--trust-insecure-ssl"]).trust_insecure_ssl
    assert parser.parse_args(["report"]).trust_insecure_ssl is False
    for offline in ("demo", "init"):  # they never connect: the flag would only mislead
        with pytest.raises(SystemExit):
            parser.parse_args([offline, "--trust-insecure-ssl"])
    capsys.readouterr()


def test_config_file_and_environment_cannot_turn_it_on(made, monkeypatch, tmp_path, capsys):
    (tmp_path / "firefly-reports.toml").write_text("trust_insecure_ssl = true\n")
    monkeypatch.setenv("FIREFLY_TRUST_INSECURE_SSL", "1")
    assert main(REPORT) == 0
    assert made[-1]["trust_insecure_ssl"] is False
    assert "trust_insecure_ssl" in capsys.readouterr().err  # only the unknown-key warning


def test_the_client_receives_a_notice_callback(made):
    assert main(REPORT) == 0
    assert callable(made[-1]["on_notice"])


@pytest.mark.parametrize("lang", ["en", "it"])
@pytest.mark.parametrize(
    ("kind", "detail"),
    [("insecure", ""), ("warn_list", "emSign Root CA - G1"), ("unchecked", "no chain API")],
)
def test_each_notice_prints_on_stderr_and_encodes_in_cp1252(lang, kind, detail, capsys):
    i18n.load(lang)
    print_trust_notice(TrustNotice(kind, "firefly.example.org", detail))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(("WARNING", "ATTENZIONE"))
    assert "firefly.example.org" in captured.err
    if detail:
        assert detail in captured.err
    captured.err.encode("cp1252")


def test_the_languages_word_the_notices_differently():
    seen = {}
    for lang in ("en", "it"):
        i18n.load(lang)
        for kind in ("insecure", "warn_list", "unchecked"):
            seen[(lang, kind)] = i18n.t(f"cli.trust_{kind}")
    for kind in ("insecure", "warn_list", "unchecked"):
        assert seen[("en", kind)] != seen[("it", kind)]


class Blocked:
    def __getattr__(self, name):
        def call(*args, **kwargs):
            raise UntrustedChainError(
                host="firefly.example.org",
                label="Weak CA",
                reason="key compromised",
                spki="ab" * 32,
            )

        return call


def test_blocked_chain_is_exit_1_with_the_error_on_stderr(tmp_path):
    code, out, err = run_main([*REPORT], tmp_path, Blocked())
    assert code == 1 and "Traceback" not in err
    assert err.startswith("Error: ") and "Weak CA" in err and "Nothing was sent" in err
    assert "All reports written" not in out


def test_blocked_chain_message_follows_the_language(tmp_path):
    code, _, err = run_main([*REPORT, "--lang", "it"], tmp_path, Blocked())
    assert code == 1 and "rifiutata" in err and "Weak CA" in err


def test_connect_passes_the_flag_through_the_library_api():
    assert connect("https://firefly.example.org", "t").session.verify is True
    assert (
        connect("https://firefly.example.org", "t", trust_insecure_ssl=True).session.verify is False
    )
