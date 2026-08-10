"""Unit tests for config.py."""

import tomllib

import pytest

from firefly_reports import config as cfg


def test_load_config_returns_empty_when_no_file(tmp_path, monkeypatch):
    """load_config() returns {} when firefly-reports.toml does not exist."""
    monkeypatch.chdir(tmp_path)
    result = cfg.load_config()
    assert result == {}


def test_load_config_reads_toml_values(tmp_path, monkeypatch):
    """load_config() parses a valid TOML file and returns its contents."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "firefly-reports.toml"
    config_file.write_text(
        'url = "https://firefly.example.com"\n'
        'owner = "Test User"\n'
        'currency = "€"\n'
        'lang = "en"\n'
        "legacy_report = true\n"
        'tags = ["tax", "business"]\n',
        encoding="utf-8",
    )
    result = cfg.load_config()
    assert result["url"] == "https://firefly.example.com"
    assert result["owner"] == "Test User"
    assert result["currency"] == "€"
    assert result["lang"] == "en"
    assert result["legacy_report"] is True
    assert result["tags"] == ["tax", "business"]


def test_load_config_raises_on_malformed_toml(tmp_path, monkeypatch):
    """load_config() propagates TOMLDecodeError on invalid syntax."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "firefly-reports.toml"
    config_file.write_text("this is not = valid = toml\n", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        cfg.load_config()
