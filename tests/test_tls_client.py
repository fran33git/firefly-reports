"""The TLS chain check in FireflyClient: refuse before any request byte, warn, or pass."""

import logging
import platform
import warnings

import pytest
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.exceptions import InsecureRequestWarning

from firefly_reports import firefly_client
from firefly_reports.errors import UntrustedChainError
from firefly_reports.firefly_client import FireflyClient, TrustNotice, TrustWarning
from firefly_reports.tlstrust.lists import TrustEntry
from firefly_reports.tlstrust.spki import spki_sha256
from tests.tls_helpers import FakeTlsSocket, cert_der, make_cert

HOST = "firefly.example.org"
URL = f"https://{HOST}"
TOKEN = "SECRET-TOKEN-1234"


@pytest.fixture
def ders(tmp_path):
    """[leaf, intermediate, root] as three distinct real certificates."""
    return [cert_der(make_cert(tmp_path, name=n)[0]) for n in ("leaf", "inter", "root")]


@pytest.fixture
def serve(monkeypatch):
    """Make every TLS connect() succeed with a fake socket whose chain is given per host."""
    chains: dict[str, list[bytes] | None] = {}
    socks: list[FakeTlsSocket] = []

    def fake_connect(self):
        sock = FakeTlsSocket(chains[getattr(self, "_tunnel_host", None) or self.host])
        socks.append(sock)
        self.sock = sock

    monkeypatch.setattr(HTTPSConnection, "connect", fake_connect)
    return chains, socks


def _lists(monkeypatch, *entries: tuple[bytes, str, str]) -> None:
    table = tuple(
        TrustEntry(spki_sha256(der), label, level, "test reason", ("https://example.org",), "d")
        for der, label, level in entries
    )
    monkeypatch.setattr(firefly_client, "ENTRIES", table)


def _connect(client: FireflyClient, url: str = URL) -> HTTPSConnection:
    adapter = client.session.get_adapter(url)
    conn = adapter.poolmanager.connection_from_url(url)._new_conn()
    conn.connect()
    return conn


def test_blocked_intermediate_is_refused_before_any_request_byte(serve, ders, monkeypatch):
    chains, socks = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch, (ders[1], "Weak Intermediate", "block"))
    client = FireflyClient(URL, TOKEN)
    with pytest.raises(UntrustedChainError) as err:
        _connect(client)
    assert "Weak Intermediate" in str(err.value) and HOST in str(err.value)
    assert socks[0].sent == [] and socks[0].closed


def test_clean_chain_connects_silently(serve, ders, monkeypatch):
    chains, socks = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch)
    notices: list[TrustNotice] = []
    conn = _connect(FireflyClient(URL, TOKEN, on_notice=notices.append))
    assert notices == [] and conn.sock is socks[0] and not socks[0].closed


def test_warn_entry_connects_and_warns_once_per_host(serve, ders, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch, (ders[2], "Some Root", "warn"))
    notices: list[TrustNotice] = []
    client = FireflyClient(URL, TOKEN, on_notice=notices.append)
    _connect(client)
    _connect(client)
    assert notices == [TrustNotice("warn_list", "firefly.example.org", "Some Root")]


def test_empty_chain_connects_with_an_unchecked_warning(serve, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = []
    _lists(monkeypatch)
    notices: list[TrustNotice] = []
    _connect(FireflyClient(URL, TOKEN, on_notice=notices.append))
    assert [n.kind for n in notices] == ["unchecked"]
    assert "resumed" in notices[0].detail


def test_socket_without_chain_api_connects_with_an_unchecked_warning(serve, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = None
    _lists(monkeypatch)
    notices: list[TrustNotice] = []
    _connect(FireflyClient(URL, TOKEN, on_notice=notices.append))
    assert [n.kind for n in notices] == ["unchecked"]
    assert "no chain API" in notices[0].detail


def test_malformed_certificate_is_unchecked_but_a_blocked_one_still_blocks(
    serve, ders, monkeypatch
):
    chains, _ = serve
    chains["firefly.example.org"] = [ders[0], b"\x30\x03bad", ders[2]]
    _lists(monkeypatch)
    notices: list[TrustNotice] = []
    _connect(FireflyClient(URL, TOKEN, on_notice=notices.append))
    assert [n.kind for n in notices] == ["unchecked"] and "could not be read" in notices[0].detail
    _lists(monkeypatch, (ders[2], "Weak Root", "block"))
    with pytest.raises(UntrustedChainError):
        _connect(FireflyClient(URL, TOKEN))


def test_every_host_is_checked_on_its_own_connection(serve, ders, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = [ders[0]]  # clean
    chains["other.example.net"] = ders  # carries the blocked key
    _lists(monkeypatch, (ders[1], "Weak Intermediate", "block"))
    manager = FireflyClient(URL, TOKEN).session.get_adapter(URL).poolmanager
    manager.connection_from_url(URL)._new_conn().connect()
    with pytest.raises(UntrustedChainError) as err:
        manager.connection_from_url("https://other.example.net")._new_conn().connect()
    assert err.value.params["host"] == "other.example.net"


def test_proxy_pools_check_the_origin_chain_and_name_the_origin(serve, ders, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch, (ders[1], "Weak Intermediate", "block"))
    adapter = FireflyClient(URL, TOKEN).session.get_adapter(URL)
    pool = adapter.proxy_manager_for("http://proxy.invalid:3128").connection_from_url(URL)
    assert getattr(pool.ConnectionCls, "_firefly_trust_checked", False)
    conn = pool._new_conn()
    conn.set_tunnel(scheme="http", host="firefly.example.org", port=443)  # as _prepare_proxy does
    with pytest.raises(UntrustedChainError) as err:
        conn.connect()
    assert err.value.params["host"] == "firefly.example.org"  # the origin, never the proxy


def test_verification_is_on_by_default_and_the_adapter_is_mounted():
    client = FireflyClient(URL, TOKEN)
    assert client.session.verify is True
    adapter = client.session.get_adapter(URL)
    assert isinstance(adapter, HTTPAdapter) and type(adapter) is not HTTPAdapter


def test_trust_insecure_ssl_turns_everything_off_with_one_notice(serve, ders, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch, (ders[1], "Weak Intermediate", "block"))
    notices: list[TrustNotice] = []
    client = FireflyClient(URL, TOKEN, trust_insecure_ssl=True, on_notice=notices.append)
    assert client.session.verify is False
    assert notices == [TrustNotice("insecure", "firefly.example.org", "")]
    _connect(client)  # a blocked key does not stop a connection the user chose to leave unverified
    assert notices == [TrustNotice("insecure", "firefly.example.org", "")]


def test_trust_insecure_ssl_says_nothing_for_a_plain_http_url():
    notices: list[TrustNotice] = []
    FireflyClient("http://firefly.local", TOKEN, trust_insecure_ssl=True, on_notice=notices.append)
    assert notices == []


def test_urllib3_warning_is_replaced_by_the_project_notice(monkeypatch):
    notices: list[TrustNotice] = []
    client = FireflyClient(URL, TOKEN, trust_insecure_ssl=True, on_notice=notices.append)

    class Resp:
        status_code = 200
        content = b"{}"

        def raise_for_status(self):
            pass

        def json(self):
            return {}

    def noisy_get(*args, **kwargs):
        warnings.warn("unverified HTTPS request", InsecureRequestWarning, stacklevel=1)
        return Resp()

    monkeypatch.setattr(client.session, "get", noisy_get)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        client._get("about")
    assert [w for w in seen if issubclass(w.category, InsecureRequestWarning)] == []


def test_debug_log_explains_each_step_and_never_logs_the_token(serve, ders, monkeypatch, caplog):
    chains, _ = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch, (ders[2], "Some Root", "warn"))
    with caplog.at_level(logging.DEBUG, logger="firefly_reports.client"):
        _connect(FireflyClient(URL, TOKEN, on_notice=lambda notice: None))
    text = caplog.text
    assert "TLS chain for firefly.example.org: path=private certs=3" in text
    assert spki_sha256(ders[0]) in text and "Some Root" in text
    assert "verdict" in text and "lists" in text
    assert f"Python {platform.python_version()}" in text and "OpenSSL" in text
    assert TOKEN not in text


def test_a_blocked_chain_is_never_swallowed_by_the_deep_fetch(monkeypatch):
    client = FireflyClient(URL, TOKEN, request_delay=0)

    def blocked(journal_id):
        raise UntrustedChainError(host="h", label="L", reason="r", spki="ab" * 32)

    monkeypatch.setattr(client, "get_transaction_journal_by_id", blocked)
    with pytest.raises(UntrustedChainError):
        client.fetch_link_details(["1", "2"])


def test_without_a_callback_an_unchecked_chain_becomes_a_python_warning(serve, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = None
    _lists(monkeypatch)
    with pytest.warns(TrustWarning, match=r"firefly\.example\.org.*could not be checked"):
        _connect(FireflyClient(URL, TOKEN))


def test_without_a_callback_a_warn_entry_becomes_a_python_warning(serve, ders, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch, (ders[2], "Some Root", "warn"))
    with pytest.warns(TrustWarning, match="Some Root"):
        _connect(FireflyClient(URL, TOKEN))


def test_without_a_callback_trust_insecure_ssl_warns_loudly():
    with pytest.warns(TrustWarning, match=r"firefly\.example\.org.*not verified"):
        FireflyClient(URL, TOKEN, trust_insecure_ssl=True)


def test_with_a_callback_no_python_warning_is_added(serve, ders, monkeypatch):
    chains, _ = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch, (ders[2], "Some Root", "warn"))
    notices: list[TrustNotice] = []
    with warnings.catch_warnings():
        warnings.simplefilter("error", TrustWarning)
        _connect(FireflyClient(URL, TOKEN, on_notice=notices.append))
        FireflyClient(URL, TOKEN, trust_insecure_ssl=True, on_notice=notices.append)
    assert [n.kind for n in notices] == ["warn_list", "insecure"]


def test_session_survives_deepcopy_and_stays_checked(serve, ders, monkeypatch):
    import copy

    chains, _ = serve
    chains["firefly.example.org"] = ders
    _lists(monkeypatch, (ders[1], "Bad Intermediate", "block"))
    client = FireflyClient(URL, TOKEN)
    client.session = copy.deepcopy(client.session)
    with pytest.raises(UntrustedChainError):
        _connect(client)


def test_secure_client_does_not_touch_the_warnings_filters(monkeypatch):
    client = FireflyClient(URL, TOKEN)
    seen = []
    monkeypatch.setattr(
        client.session, "get", lambda url, **kw: seen.append(list(warnings.filters))
    )
    before = list(warnings.filters)
    client._http_get(f"{URL}/x")
    assert seen == [before]
