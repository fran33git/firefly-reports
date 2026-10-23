"""``[export]`` config section: CLI > config file > default, and unknown-key warnings."""

import json
from pathlib import Path
from unittest import mock

import pytest

from firefly_reports import i18n
from firefly_reports.cli import build_parser
from firefly_reports.cli import main as cli_main
from firefly_reports.cli.export import resolve_export_settings
from firefly_reports.errors import ConfigurationError
from firefly_reports.firefly_client import FireflyClient

FIXTURE = Path(__file__).parent.parent / "fixtures" / "firefly_transactions.json"


def settings(argv=(), config=None):
    args = build_parser().parse_args(["export", "beancount", *argv])
    return resolve_export_settings(args, config or {})


@pytest.mark.parametrize(
    ("argv", "config", "attr", "expected"),
    [
        ([], {}, "out", Path("ledger")),
        ([], {"export": {"out": "books"}}, "out", Path("books")),
        (["--out", "cli"], {"export": {"out": "books"}}, "out", Path("cli")),
        # the top-level `out` belongs to `report`
        ([], {"out": "./output"}, "out", Path("ledger")),
        ([], {}, "layout", "yearly"),
        ([], {"export": {"layout": "single"}}, "layout", "single"),
        (["--layout", "yearly"], {"export": {"layout": "single"}}, "layout", "yearly"),
        ([], {}, "classify_by", None),
        ([], {"export": {"classify_by": "account"}}, "classify_by", "account"),
        (
            ["--classify-by", "category"],
            {"export": {"classify_by": "account"}},
            "classify_by",
            "category",
        ),
        ([], {}, "map", None),
        ([], {"export": {"map": "m.yaml"}}, "map", "m.yaml"),
        (["--map", "cli.yaml"], {"export": {"map": "m.yaml"}}, "map", "cli.yaml"),
    ],
)
def test_precedence(argv, config, attr, expected):
    assert getattr(settings(argv, config), attr) == expected


@pytest.mark.parametrize(
    ("section", "key"),
    [({"layout": "monthly"}, "export.layout"), ({"classify_by": "tag"}, "export.classify_by")],
)
def test_invalid_config_choice_is_a_configuration_error(section, key):
    with pytest.raises(ConfigurationError) as exc:
        settings(config={"export": section})
    assert key in str(exc.value)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for var in ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("firefly_reports.cli._options.load_dotenv", lambda *a, **k: None)
    yield tmp_path
    i18n.load("en")


@pytest.fixture
def client():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    splits = FireflyClient._flatten_transactions(None, payload["data"])  # type: ignore[arg-type]
    with mock.patch("firefly_reports.cli._options.FireflyClient") as cls:
        cls.return_value.get_transactions.return_value = splits
        yield cls.return_value


def test_export_uses_config_section_end_to_end(env, client):
    (env / "firefly-reports.toml").write_text(
        'url = "https://firefly.example.com"\ntoken = "tok"\n'
        '[export]\nout = "books"\nlayout = "single"\n',
        encoding="utf-8",
    )
    assert cli_main(["export", "beancount", "--allow-unmapped", "--no-timestamp"]) == 0
    assert [p.name for p in (env / "books").iterdir()] == ["firefly.beancount"]
    assert not (env / "ledger").exists()


def test_unknown_config_key_warns_on_stderr_and_still_runs(env, client, capsys):
    (env / "firefly-reports.toml").write_text(
        'url = "https://firefly.example.com"\ntoken = "tok"\nouptut = "x"\n'
        '[export]\nlayuot = "single"\n',
        encoding="utf-8",
    )
    assert cli_main(["export", "beancount", "--dry-run", "--allow-unmapped"]) == 0
    err = capsys.readouterr().err
    assert "unknown key 'ouptut'" in err
    assert "Did you mean 'export.layout'?" in err


def test_unknown_config_key_warning_is_translated(env, client, capsys):
    (env / "firefly-reports.toml").write_text(
        'url = "https://firefly.example.com"\ntoken = "tok"\nlang = "it"\nzzzz = 1\n',
        encoding="utf-8",
    )
    cli_main(["export", "beancount", "--dry-run", "--allow-unmapped"])
    assert "sconosciuta" in capsys.readouterr().err
