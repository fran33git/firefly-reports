"""Export of Firefly transaction links as shared ^links (offline)."""

import json
from pathlib import Path

import pytest
import requests

from firefly_reports import i18n
from firefly_reports.firefly_client import FireflyClient
from firefly_reports.ledger.export import LAYOUT_SINGLE, run_export
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import parse_ledger_config
from tests.ledger_helpers import export_request

FIXTURE = Path(__file__).parent / "fixtures" / "firefly_transactions.json"


class Client:
    def __init__(self, splits, links=(), error=None):
        self.splits, self.links, self.error = splits, list(links), error
        self.link_calls = []

    def get_transactions(self, start=None, end=None, tx_type=None):
        return self.splits

    def get_transaction_links(self, resolve_types=True):
        self.link_calls.append(resolve_types)
        if self.error:
            raise self.error
        return self.links


@pytest.fixture
def splits():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return FireflyClient._flatten_transactions(None, payload["data"])  # type: ignore[arg-type]


@pytest.fixture
def labels():
    i18n.load("en")
    return LedgerLabels.from_i18n()


def request(out, **kw):
    return export_request(
        None, None, out, parse_ledger_config({}), layout=LAYOUT_SINGLE, timestamp=False, **kw
    )


def test_run_export_adds_links_and_requests_no_types(splits, labels, tmp_path):
    ids = [s["transaction_journal_id"] for s in splits[:2]]
    client = Client(splits, [{"id": "5", "inward_id": ids[0], "outward_id": ids[1]}])
    assert run_export(client, request(tmp_path), labels) == 0
    text = (tmp_path / "firefly.beancount").read_text()
    assert text.count("^firefly-link-5") == 2
    assert client.link_calls == [False]


def test_skipped_links_are_reported_once_on_stderr(splits, labels, tmp_path, capsys):
    links = [{"id": "5", "inward_id": "999", "outward_id": "998"}]
    assert run_export(Client(splits, links), request(tmp_path), labels) == 0
    err = capsys.readouterr().err
    assert err.count("1") >= 1 and "link" in err.lower()


def test_no_links_means_no_warning(splits, labels, tmp_path, capsys):
    assert run_export(Client(splits), request(tmp_path), labels) == 0
    assert "link" not in capsys.readouterr().err.lower()


def test_link_fetch_error_propagates_before_writing(splits, labels, tmp_path):
    client = Client(splits, error=requests.ConnectionError("down"))
    with pytest.raises(requests.ConnectionError):
        run_export(client, request(tmp_path / "out"), labels)
    assert not (tmp_path / "out").exists()
