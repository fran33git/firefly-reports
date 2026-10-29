"""SHA-256 of the SubjectPublicKeyInfo of a DER certificate, with the standard library only.

A CA incident compromises a *key*; a reissued certificate keeps the same key, so keys (not
certificates) are what the trust lists name. Only the fixed path to the SPKI is parsed
(RFC 5280 section 4.1); every read is bounds-checked and anything unexpected is a ``ValueError``.
"""

from __future__ import annotations

import hashlib

_SEQUENCE = 0x30
_BIT_STRING = 0x03
_VERSION = 0xA0  # [0] EXPLICIT, present when the certificate is not v1


def _tlv(data: bytes, pos: int, limit: int) -> tuple[int, int, int]:
    """Tag, content start and content end of the element at *pos*, which must end by *limit*."""
    if pos + 2 > limit:
        raise ValueError("truncated DER")
    tag = data[pos]
    if tag & 0x1F == 0x1F:
        raise ValueError("high tag numbers are not used in certificates")
    first = data[pos + 1]
    start = pos + 2
    if first < 0x80:
        length = first
    else:
        count = first & 0x7F
        if count == 0 or count > 4:
            raise ValueError("unsupported DER length form")
        if start + count > limit:
            raise ValueError("truncated DER")
        length = int.from_bytes(data[start : start + count], "big")
        start += count
    end = start + length
    if end > limit:
        raise ValueError("DER length beyond the buffer")
    return tag, start, end


def spki_sha256(der_cert: bytes) -> str:
    """Lowercase hex SHA-256 of the DER SubjectPublicKeyInfo of *der_cert*."""
    tag, cert_start, cert_end = _tlv(der_cert, 0, len(der_cert))
    if tag != _SEQUENCE:
        raise ValueError("a certificate is a DER SEQUENCE")
    tag, tbs_start, tbs_end = _tlv(der_cert, cert_start, cert_end)
    if tag != _SEQUENCE:
        raise ValueError("TBSCertificate is a DER SEQUENCE")

    pos = tbs_start
    tag, _, end = _tlv(der_cert, pos, tbs_end)
    if tag == _VERSION:
        pos = end
    for _ in range(5):  # serialNumber, signature, issuer, validity, subject
        _, _, pos = _tlv(der_cert, pos, tbs_end)

    tag, spki_start, spki_end = _tlv(der_cert, pos, tbs_end)
    if tag != _SEQUENCE:
        raise ValueError("SubjectPublicKeyInfo is a DER SEQUENCE")
    tag, _, alg_end = _tlv(der_cert, spki_start, spki_end)
    if tag != _SEQUENCE:
        raise ValueError("SubjectPublicKeyInfo starts with the algorithm SEQUENCE")
    tag, _, _ = _tlv(der_cert, alg_end, spki_end)
    if tag != _BIT_STRING:
        raise ValueError("SubjectPublicKeyInfo ends with the key BIT STRING")
    return hashlib.sha256(der_cert[pos:spki_end]).hexdigest()
