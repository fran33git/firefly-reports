"""``export beancount`` end to end for both layouts (no timestamp), pinned by golden snapshots."""

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from firefly_reports.firefly_client import FireflyClient
from tests.golden.harness import run_main
from tests.golden.snapshot import assert_golden

FIXTURE = Path(__file__).parent / "fixtures" / "firefly_transactions.json"
CREDS = ["--url", "https://demo.invalid", "--token", "x"]


def _splits():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return FireflyClient._flatten_transactions(None, payload["data"])  # type: ignore[arg-type]


@pytest.mark.golden
@pytest.mark.parametrize("layout", ["yearly", "single"])
def test_ledger_export_matches_golden(layout, tmp_path):
    out = tmp_path / "ledger"
    client = mock.MagicMock()
    client.get_transactions.return_value = _splits()
    client.get_transaction_links.return_value = []
    argv = ["export", "beancount", *CREDS, "--layout", layout, "--out", str(out)]
    argv += ["--no-timestamp", "--allow-unmapped"]
    code, _, _ = run_main(argv, tmp_path / "cwd", client)
    assert code == 0, os.listdir(tmp_path)
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted(out.iterdir())}
    assert_golden(f"ledger/{layout}", files)
