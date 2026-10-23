"""The 1.x invocation form (no subcommand) keeps working, with a redacted deprecation hint."""

import pytest

from firefly_reports.cli import COMMANDS, build_parser, main
from firefly_reports.cli import _value_options as value_options
from firefly_reports.cli._legacy import command_hint, find_command, redact, rewrite_legacy
from tests.golden.harness import run_main

VALUE_OPTIONS = value_options(build_parser())
CREDS = ["--url", "https://demo.invalid", "--token", "x"]


def _find(argv):
    return find_command(argv, VALUE_OPTIONS, COMMANDS)


def test_find_command_skips_option_values():
    assert _find(["--owner", "report", "--year", "2025"]) is None
    assert _find(["--tags", "export", "--year", "2025"]) is None
    assert _find(["--lang", "it", "export", "beancount"]) == 2
    assert _find(["--owner=export", "init"]) == 1
    assert _find(["report", "--year", "2025"]) == 0
    assert _find(["--", "report"]) is None


def test_value_options_are_derived_from_the_parsers():
    assert {"--owner", "--tags", "--year", "--url", "--layout"} <= VALUE_OPTIONS
    assert "--no-pdf" not in VALUE_OPTIONS and "-h" not in VALUE_OPTIONS


@pytest.mark.parametrize(
    ("argv", "config_year", "expected"),
    [
        (["--year", "2025"], None, (["report", "--year", "2025"], True)),
        (["report", "--year", "2025"], None, (["report", "--year", "2025"], False)),
        (["--help"], None, (["--help"], False)),
        (["--version"], None, (["--version"], False)),
        ([], None, ([], False)),
        ([], 2025, (["report"], True)),
    ],
)
def test_rewrite_legacy(argv, config_year, expected):
    result = rewrite_legacy(
        argv, value_options=VALUE_OPTIONS, commands=COMMANDS, config_year=config_year
    )
    assert result == expected


def test_redact_hides_the_token_in_both_spellings():
    assert redact(["--token", "s3cret", "--year", "2025"]) == ["--token", "***", "--year", "2025"]
    assert redact(["--token=s3cret", "--year", "2025"]) == ["--token", "***", "--year", "2025"]
    assert "s3cret" not in command_hint(["--token=s3cret"])


def _run(argv, tmp_path):
    return run_main(argv, tmp_path)


def test_legacy_form_equals_report_subcommand(tmp_path):
    base = [*CREDS, "--year", "2025", "--no-pdf", "--no-excel"]
    code_legacy, out_legacy, err_legacy = _run(base, tmp_path / "a")
    code_new, out_new, err_new = _run(["report", *base], tmp_path / "b")
    assert code_legacy == code_new == 0
    assert out_legacy.replace(str(tmp_path / "a"), "X") == out_new.replace(str(tmp_path / "b"), "X")
    assert (
        "deprecated" in err_legacy
        and "firefly-reports report --url https://demo.invalid --token *** --year 2025"
        in err_legacy
    )
    assert err_new == ""


def test_legacy_hint_redacts_token(tmp_path):
    for token_args in (["--token", "s3cret"], ["--token=s3cret"]):
        _, _, err = _run(
            [
                "--url",
                "https://demo.invalid",
                *token_args,
                "--year",
                "2025",
                "--no-pdf",
                "--no-excel",
            ],
            tmp_path,
        )
        assert "--token ***" in err and "s3cret" not in err


def test_legacy_hint_is_translated(tmp_path):
    _, _, err = _run([*CREDS, "--lang", "it", "--year", "2025", "--no-pdf", "--no-excel"], tmp_path)
    assert "Attenzione:" in err and "3.0" in err


def test_bare_invocation_with_config_year_runs_report(tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "firefly-reports.toml").write_text(
        'url = "https://demo.invalid"\ntoken = "x"\nyear = 2025\n[tax]\ndeductible_keywords = ["a"]\n',
        encoding="utf-8",
    )
    code, out, err = run_main([], cwd)
    assert code == 0 and "Summary 2025-01-01 -> 2025-12-31" in out
    assert "deprecated" in err


def test_bare_invocation_without_config_prints_help_exit_2(tmp_path, capsys):
    code, out, _ = run_main([], tmp_path)
    assert code == 2 and "usage: firefly-reports" in out


def test_main_accepts_an_explicit_argv(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("firefly_reports.cli._options.load_dotenv", lambda *a, **k: None)
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "firefly-reports 2.0.0" in capsys.readouterr().out


def test_redact_hides_abbreviated_token_spellings():
    """argparse accepts unique prefixes, so `--tok X` and `--toke=X` must be masked too."""
    assert redact(["--tok", "s3cret", "--year", "2025"]) == ["--tok", "***", "--year", "2025"]
    assert redact(["--toke=s3cret"]) == ["--toke", "***"]
    assert redact(["--tags", "tax"]) == ["--tags", "tax"]  # a different option is untouched


def test_hint_masks_credentials_in_the_url():
    hint = command_hint(["--url", "https://user:pw@firefly.example.com", "--year", "2025"])
    assert "pw" not in hint and "user" not in hint and "https://***@firefly.example.com" in hint
    assert "https://firefly.example.com" in command_hint(["--url=https://firefly.example.com"])


def test_hint_quoting_is_platform_aware():
    argv = ["--owner", "Mario Rossi", "--token", "x"]
    assert command_hint(argv, windows=False) == (
        "firefly-reports report --owner 'Mario Rossi' --token ***"
    )
    assert command_hint(argv, windows=True) == (
        'firefly-reports report --owner "Mario Rossi" --token ***'
    )
