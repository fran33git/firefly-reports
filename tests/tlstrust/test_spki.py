import pytest

from firefly_reports.tlstrust.spki import spki_sha256
from tests.tls_helpers import cert_der, make_cert, openssl_spki_sha256


@pytest.mark.parametrize("algo", ["rsa", "ec"])
def test_matches_openssl_for_rsa_and_ec_certs(tmp_path, algo):
    cert, _ = make_cert(tmp_path, algo=algo)
    assert spki_sha256(cert_der(cert)) == openssl_spki_sha256(cert)


def test_result_is_lowercase_hex_sha256(tmp_path):
    cert, _ = make_cert(tmp_path)
    digest = spki_sha256(cert_der(cert))
    assert len(digest) == 64 and digest == digest.lower()
    int(digest, 16)


def test_rejects_truncated_der(tmp_path):
    cert, _ = make_cert(tmp_path)
    der = cert_der(cert)
    for cut in (len(der) // 2, 30, 4, 1):
        with pytest.raises(ValueError):
            spki_sha256(der[:cut])


def test_rejects_non_sequence():
    with pytest.raises(ValueError):
        spki_sha256(b"\x04\x03abc")


def test_rejects_empty():
    with pytest.raises(ValueError):
        spki_sha256(b"")


def test_rejects_length_beyond_buffer():
    with pytest.raises(ValueError):
        spki_sha256(b"\x30\x84\xff\xff\xff\xff\x00")
