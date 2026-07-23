from __future__ import annotations

import hashlib
import hmac

import keyring
from cryptography.fernet import Fernet

_SERVICE = "AutoZoopla"
_KEY_NAME = "encryption-key"


def _get_or_create_key() -> bytes:
    """Return the app's symmetric key, generating + storing it on first use.

    The key lives in the OS keychain (macOS Keychain / Windows Credential
    Manager) via ``keyring`` and never touches the project directory.
    """

    existing = keyring.get_password(_SERVICE, _KEY_NAME)
    if existing:
        return existing.encode("ascii")
    key = Fernet.generate_key()
    keyring.set_password(_SERVICE, _KEY_NAME, key.decode("ascii"))
    return key


def get_cipher() -> Fernet:
    """A Fernet cipher keyed by the keychain-stored app key."""

    return Fernet(_get_or_create_key())


def hash_name(*parts: str) -> str:
    """Derive an opaque, stable filename fragment from the given parts.

    HMAC-SHA256 keyed by the app key, so the value cannot be correlated to the
    inputs (e.g. an account email) without the keychain secret.
    """

    key = _get_or_create_key()
    message = "|".join(parts).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:32]
