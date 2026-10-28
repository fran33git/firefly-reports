import ssl

from firefly_reports.tlstrust.chain import ChainRead, read_verified_chain

CHAIN = [b"leaf-der", b"intermediate-der", b"root-der"]


class FakeCertificate:
    """Stands in for ``ssl._ssl.Certificate`` (what the private binding returns)."""

    def __init__(self, der: bytes) -> None:
        self._der = der

    def public_bytes(self) -> str:
        return ssl.DER_cert_to_PEM_cert(self._der)


class PublicSocket:
    def get_verified_chain(self):
        return list(CHAIN)


class _SslObj:
    def __init__(self, chain):
        self._chain = chain

    def get_verified_chain(self):
        if isinstance(self._chain, Exception):
            raise self._chain
        return self._chain


class PrivateSocket:
    def __init__(self, chain=None):
        self._sslobj = _SslObj([FakeCertificate(c) for c in CHAIN] if chain is None else chain)


def test_public_api_is_used_when_present():
    read = read_verified_chain(PublicSocket())
    assert read == ChainRead(tuple(CHAIN), "public", None)
    assert read.checked


def test_private_binding_is_converted_to_der():
    read = read_verified_chain(PrivateSocket())
    assert read.path == "private"
    assert read.certs == tuple(CHAIN)
    assert read.checked


def test_both_paths_return_the_same_certificates():
    assert read_verified_chain(PublicSocket()).certs == read_verified_chain(PrivateSocket()).certs


def test_public_api_wins_when_both_exist():
    class Both(PublicSocket, PrivateSocket):
        pass

    assert read_verified_chain(Both()).path == "public"


def test_no_binding_is_unavailable_with_a_reason():
    read = read_verified_chain(object())
    assert read.path == "unavailable"
    assert read.certs == ()
    assert not read.checked
    assert read.reason and "no chain API" in read.reason


def test_empty_chain_is_not_checked_and_says_why():
    read = read_verified_chain(PrivateSocket(chain=[]))
    assert read.certs == ()
    assert not read.checked
    assert read.reason and "resumed" in read.reason


def test_a_failing_binding_never_propagates():
    read = read_verified_chain(PrivateSocket(chain=RuntimeError("boom")))
    assert read.path == "unavailable"
    assert not read.checked
    assert read.reason and "RuntimeError" in read.reason


def test_a_certificate_that_cannot_be_converted_is_unavailable():
    read = read_verified_chain(PrivateSocket(chain=[object()]))
    assert read.path == "unavailable"
    assert not read.checked
