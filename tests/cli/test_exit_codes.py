"""Exit codes and streams: errors on stderr, 3 for partial failures, 130 on Ctrl-C."""

import pytest
import requests

from firefly_reports.cli import main
from tests.golden.harness import run_main

CREDS = ["--url", "https://demo.invalid", "--token", "x"]
BASE = ["report", *CREDS, "--year", "2025", "--no-pdf", "--no-excel"]


def test_success_is_exit_0(tmp_path):
    code, out, err = run_main(BASE, tmp_path)
    assert (code, err) == (0, "") and "All reports written" in out


def test_errors_go_to_stderr_with_exit_1(tmp_path):
    code, out, err = run_main(["report", "--token", "x", "--year", "2025"], tmp_path)
    assert code == 1 and out == "" and err.startswith("Error: ") and "URL is required" in err


def test_translated_errors_follow_the_language(tmp_path):
    code, _, err = run_main(["report", "--lang", "it", "--token", "x", "--year", "2025"], tmp_path)
    assert code == 1 and "obbligatorio" in err


def test_exit_code_3_when_a_file_fails(tmp_path):
    from unittest import mock

    with mock.patch("firefly_reports.reports.pipeline.write_workbook", side_effect=OSError("disk")):
        code, out, _ = run_main(["report", *CREDS, "--year", "2025", "--no-pdf"], tmp_path)
    assert code == 3 and "files failed" in out


def test_api_error_exit_1_without_traceback(tmp_path):
    class Down:
        def __getattr__(self, name):
            def call(*args, **kwargs):
                raise requests.ConnectionError("unreachable")

            return call

    code, out, err = run_main(BASE, tmp_path, Down())
    assert code == 1 and "Traceback" not in err and err.startswith("Error: ")
    assert "unreachable" in err


def test_keyboard_interrupt_exit_130(tmp_path):
    class Interrupted:
        def __getattr__(self, name):
            def call(*args, **kwargs):
                raise KeyboardInterrupt

            return call

    code, _, _ = run_main(BASE, tmp_path, Interrupted())
    assert code == 130


def test_usage_error_exits_2(tmp_path):
    code, _, _ = run_main(["report", "--years", "4"], tmp_path)
    assert code == 2


def test_malformed_config_exit_1(tmp_path):
    (tmp_path / "firefly-reports.toml").write_text("not = [valid", encoding="utf-8")
    code, out, err = run_main(["report", *CREDS, "--year", "2025"], tmp_path)
    assert code == 1 and out == "" and "malformed" in err


@pytest.mark.parametrize("flag", ["--version"])
def test_version_flag(flag, tmp_path, capsys):
    code, out, _ = run_main([flag], tmp_path)
    assert code == 0 and out.strip() == "firefly-reports 2.0.0"


def test_python_m_firefly_reports_help():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "firefly_reports", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    for command in ("report", "export", "init", "demo"):
        assert command in proc.stdout


def test_cli_help_does_not_import_renderers():
    import subprocess
    import sys

    code = (
        "from firefly_reports.cli import main\n"
        "try:\n    main(['--help'])\nexcept SystemExit:\n    pass\n"
        "import sys\nheavy = {'matplotlib', 'reportlab'} & set(sys.modules)\nassert not heavy, heavy\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)


def test_init_subcommand_dispatches(tmp_path, monkeypatch):
    from unittest import mock

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("firefly_reports.cli._options.load_dotenv", lambda *a, **k: None)
    with mock.patch("firefly_reports.cli.run_init") as run_init:
        assert main(["init"]) == 0
    run_init.assert_called_once()
