"""The ``init`` wizard (./firefly-reports.toml)."""

import getpass
import stat

from firefly_reports.cli.init import run_init


def _mock_wizard(monkeypatch, inputs, token=""):
    """Feed scripted answers to input() and a fixed token to getpass."""
    answers = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": token)


def test_init_aborts_when_user_declines_overwrite(tmp_path, monkeypatch, capsys):
    """An existing config is kept when the user does not answer 'y'."""
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "firefly-reports.toml"
    cfg.write_text("old = true\n", encoding="utf-8")
    _mock_wizard(monkeypatch, ["n"])
    run_init()
    assert cfg.read_text(encoding="utf-8") == "old = true\n"
    assert "Aborted" in capsys.readouterr().out


def test_init_happy_path_with_token(tmp_path, monkeypatch, capsys):
    """Answers are written to the TOML file with owner-only permissions."""
    monkeypatch.chdir(tmp_path)
    _mock_wizard(
        monkeypatch,
        ["", "Mario Rossi", "", "IT", "y", "", "tax, business"],
        token="secret",
    )
    run_init()
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


def test_init_defaults_without_token(tmp_path, monkeypatch):
    """Blank answers fall back to defaults; the token line stays commented."""
    monkeypatch.chdir(tmp_path)
    _mock_wizard(monkeypatch, ["", "", "", "", "", "", ""])
    run_init()
    content = (tmp_path / "firefly-reports.toml").read_text(encoding="utf-8")
    assert 'url      = "https://firefly.example.com"' in content
    assert '# token = ""' in content
    assert 'token    = "' not in content
    assert 'owner    = ""' in content
    assert 'lang     = "en"' in content
    assert "legacy_report = false" in content
    assert "tags     = []" in content


def test_init_invalid_lang_falls_back_to_en(tmp_path, monkeypatch):
    """An unsupported language answer is coerced to 'en'."""
    monkeypatch.chdir(tmp_path)
    _mock_wizard(monkeypatch, ["", "", "", "fr", "", "", ""])
    run_init()
    content = (tmp_path / "firefly-reports.toml").read_text(encoding="utf-8")
    assert 'lang     = "en"' in content


def test_init_overwrite_accepted(tmp_path, monkeypatch):
    """Answering 'y' rewrites an existing config file."""
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "firefly-reports.toml"
    cfg.write_text("old = true\n", encoding="utf-8")
    _mock_wizard(monkeypatch, ["y", "", "", "", "", "", "", ""])
    run_init()
    content = cfg.read_text(encoding="utf-8")
    assert "old = true" not in content
    assert 'url      = "https://firefly.example.com"' in content


def test_init_no_warning_when_gitignore_covers_config(tmp_path, monkeypatch, capsys):
    """No .gitignore warning is printed when the config file is already ignored."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("firefly-reports.toml\n", encoding="utf-8")
    _mock_wizard(monkeypatch, ["", "", "", "", "", "", ""], token="secret")
    run_init()
    assert "WARNING" not in capsys.readouterr().out


def test_init_template_lists_only_known_keys(tmp_path, monkeypatch):
    """The commented template parses as valid TOML and uncommenting it uses only known keys."""
    import re
    import tomllib

    from firefly_reports.cli.config import unknown_keys
    from firefly_reports.cli.init import OPTIONAL_TEMPLATE

    monkeypatch.chdir(tmp_path)
    _mock_wizard(monkeypatch, ["", "", "", "", "", "", ""])
    run_init()
    written = (tmp_path / "firefly-reports.toml").read_text(encoding="utf-8")
    assert "[export]" in written and "[filters]" in written
    assert unknown_keys(tomllib.loads(written)) == []
    uncommented = re.sub(r"^# (?=\w+ *=)", "", OPTIONAL_TEMPLATE, flags=re.MULTILINE)
    parsed = tomllib.loads(uncommented)
    assert unknown_keys(parsed) == []
    assert set(parsed) == {"year", "reports", "filters", "tax", "export"}
