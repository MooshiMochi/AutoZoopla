"""Test-wide fixtures.

Force an in-memory keyring backend so encryption tests never read from or
write to the developer's real OS keychain.
"""

from __future__ import annotations

import keyring
import pytest
from keyring.backend import KeyringBackend


class _MemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


@pytest.fixture(autouse=True)
def _memory_keyring():
    from relister.core import security

    previous = keyring.get_keyring()
    keyring.set_keyring(_MemoryKeyring())
    security._reset_key_cache()
    yield
    security._reset_key_cache()
    keyring.set_keyring(previous)
