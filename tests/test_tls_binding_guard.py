"""Guard for invariant 6: the chain must stay readable on the Pythons we support.

If the private OpenSSL binding disappears on 3.11/3.12 (or the public API changes on 3.13+) the
trust check would silently degrade to "not checked"; this test makes that loud in CI.
"""

import socket
import ssl
import sys
import threading

from firefly_reports.tlstrust.chain import read_verified_chain
from tests.tls_helpers import cert_der, make_cert


def test_real_handshake_chain_is_readable(tmp_path, allow_loopback):
    cert, key = make_cert(tmp_path)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert, key)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def serve() -> None:
        conn, _ = listener.accept()
        try:
            with server_ctx.wrap_socket(conn, server_side=True) as tls:
                tls.recv(1)
        except OSError:
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    client_ctx = ssl.create_default_context(cafile=str(cert))
    try:
        with (
            socket.create_connection(("127.0.0.1", port), timeout=10) as raw,
            client_ctx.wrap_socket(raw, server_hostname="127.0.0.1") as tls,
        ):
            read = read_verified_chain(tls)
    finally:
        listener.close()
        thread.join(timeout=5)

    assert read.checked, read.reason
    assert read.path == ("public" if sys.version_info >= (3, 13) else "private")
    assert read.certs[0] == cert_der(cert)
