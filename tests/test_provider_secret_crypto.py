from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

import pytest

from services.api.teacher_provider_registry_service import decrypt_secret, encrypt_secret


def _legacy_v1(secret: str, master: str) -> str:
    plain = secret.encode("utf-8")
    key = hashlib.sha256(master.encode("utf-8")).digest()
    nonce = secrets.token_bytes(12)
    stream = bytearray()
    counter = 0
    while len(stream) < len(plain):
        stream.extend(hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    cipher = bytes(a ^ b for a, b in zip(plain, bytes(stream[: len(plain)])))
    tag = hmac.new(key, b"tprv-v1:" + nonce + cipher, hashlib.sha256).digest()[:16]
    raw = b"\x01" + nonce + tag + cipher
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def test_encrypt_uses_aes_gcm_version_byte() -> None:
    token = encrypt_secret("sk-live-secret", "master-key-for-tests")
    pad = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(token + pad)
    assert raw[0] == 2
    assert decrypt_secret(token, "master-key-for-tests") == "sk-live-secret"


def test_decrypt_still_reads_legacy_xor_blobs() -> None:
    legacy = _legacy_v1("sk-old-secret", "master-key-for-tests")
    assert decrypt_secret(legacy, "master-key-for-tests") == "sk-old-secret"


def test_decrypt_rejects_wrong_master_key() -> None:
    token = encrypt_secret("sk-live-secret", "master-key-for-tests")
    with pytest.raises(ValueError):
        decrypt_secret(token, "other-master")
