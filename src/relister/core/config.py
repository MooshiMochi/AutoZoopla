# src/relister/core/config.py
from __future__ import annotations

import os
from pathlib import Path

from relister.storage.credentials import CredentialStore

# Legacy .env variable names -> (provider, role) in the encrypted store.
_ENV_CREDENTIAL_MAP = {
    ("zoopla", "source"): ("ZOOPLA_SOURCE_USERNAME", "ZOOPLA_SOURCE_PASSWORD"),
    ("zoopla", "destination"): (
        "ZOOPLA_DESTINATION_USERNAME",
        "ZOOPLA_DESTINATION_PASSWORD",
    ),
}


def _read_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip().upper()] = value.strip().strip('"').strip("'")
    return result


def migrate_env_credentials(
    store: CredentialStore | None = None, env_path: Path | None = None
) -> None:
    """One-time import of legacy ``.env`` credentials into the encrypted store.

    Only fills entries that are not already present, so it is safe to call on
    every startup. After the first run the ``.env`` file can be deleted.
    """

    store = store or CredentialStore()
    env = _read_env_file(env_path or Path(".env"))
    for (provider, role), (user_key, pass_key) in _ENV_CREDENTIAL_MAP.items():
        if store.has(provider, role):
            continue
        username = env.get(user_key) or os.environ.get(user_key)
        password = env.get(pass_key) or os.environ.get(pass_key)
        if username and password:
            store.set(provider, role, username, password)
