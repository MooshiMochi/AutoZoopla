from __future__ import annotations

import base64
import hashlib
import hmac
import os

import keyring
from nacl.secret import SecretBox

_SERVICE = "AutoZoopla"
_KEY_NAME = "encryption-key"


def _get_or_create_key() -> bytes:
    """Return the app's 32-byte symmetric key, creating it on first use.

    The key lives in the OS keychain (macOS Keychain / Windows Credential
    Manager) via ``keyring`` and never touches the project directory.
    """

    existing = keyring.get_password(_SERVICE, _KEY_NAME)
    if existing:
        return base64.urlsafe_b64decode(existing)
    key = os.urandom(SecretBox.KEY_SIZE)
    keyring.set_password(
        _SERVICE, _KEY_NAME, base64.urlsafe_b64encode(key).decode("ascii")
    )
    return key


class _Cipher:
    """Authenticated encryption (XSalsa20-Poly1305) keyed by the app key.

    PyNaCl statically links libsodium, so there is no external OpenSSL to
    mis-bundle — unlike ``cryptography``, whose Rust binding dynamically links
    an OpenSSL that collided with Qt/Python copies in the frozen app.
    """

    def __init__(self, key: bytes) -> None:
        self._box = SecretBox(key)

    def encrypt(self, data: bytes) -> bytes:
        return bytes(self._box.encrypt(data))

    def decrypt(self, token: bytes) -> bytes:
        return self._box.decrypt(token)


def get_cipher() -> _Cipher:
    return _Cipher(_get_or_create_key())


def hash_name(*parts: str) -> str:
    """Derive an opaque, stable filename fragment from the given parts.

    HMAC-SHA256 keyed by the app key, so the value cannot be correlated to the
    inputs (e.g. an account email) without the keychain secret.
    """

    key = _get_or_create_key()
    message = "|".join(parts).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:32]
