"""End to end on loopback: a blocked key means the server receives zero application bytes."""

import socket
import ssl
import threading

import pytest

from firefly_reports import firefly_client
from firefly_reports.errors import UntrustedChainError
from firefly_reports.firefly_client import FireflyClient
from firefly_reports.tlstrust.lists import TrustEntry
from firefly_reports.tlstrust.spki import spki_sha256
from tests.tls_helpers import cert_der, make_cert

RESPONSE = b'{"data": {"version": "test"}}'


class Server:
    def __init__(self, cert, key):
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(cert, key)
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.received = b""
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            conn, _ = self.listener.accept()
            with self.ctx.wrap_socket(conn, server_side=True) as tls:
                data = tls.recv(65536)
                self.received += data
                if data:
                    tls.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                        b"Connection: close\r\nContent-Length: %d\r\n\r\n%s"
                        % (len(RESPONSE), RESPONSE)
                    )
        except OSError:
            pass

    def finish(self):
        self.listener.close()
        self.thread.join(timeout=10)


@pytest.fixture
def server(tmp_path, allow_loopback):
    cert, key = make_cert(tmp_path)
    srv = Server(cert, key)
    yield srv, cert
    srv.finish()


def _client(srv, cert):
    client = FireflyClient(f"https://127.0.0.1:{srv.port}", "SECRET-TOKEN", request_delay=0)
    client.session.trust_env = False  # no proxy for loopback
    client.session.verify = str(cert)  # trust the throwaway certificate, the check stays mounted
    return client


def test_allowed_chain_reaches_the_server(server, monkeypatch):
    srv, cert = server
    monkeypatch.setattr(firefly_client, "ENTRIES", ())
    assert _client(srv, cert)._get("about")["data"]["version"] == "test"
    srv.finish()
    assert b"SECRET-TOKEN" in srv.received  # the request, with its Authorization header, arrived


def test_blocked_chain_sends_zero_bytes(server, monkeypatch):
    srv, cert = server
    blocked = TrustEntry(
        spki_sha256(cert_der(cert)), "Test CA", "block", "test", ("https://example.org",), "d"
    )
    monkeypatch.setattr(firefly_client, "ENTRIES", (blocked,))
    with pytest.raises(UntrustedChainError):
        _client(srv, cert)._get("about")
    srv.finish()
    assert srv.received == b""
