from relister.core.config import migrate_env_credentials
from relister.storage.credentials import CredentialStore


def test_imports_env_credentials_when_absent(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        'ZOOPLA_SOURCE_USERNAME="src@example.com"\n'
        "ZOOPLA_SOURCE_PASSWORD=srcpass\n"
        "ZOOPLA_DESTINATION_USERNAME=dst@example.com\n"
        "ZOOPLA_DESTINATION_PASSWORD=dstpass\n",
        encoding="utf-8",
    )
    store = CredentialStore(tmp_path / "credentials.enc")

    migrate_env_credentials(store, env_path=env)

    assert store.get("zoopla", "source") == ("src@example.com", "srcpass")
    assert store.get("zoopla", "destination") == ("dst@example.com", "dstpass")


def test_does_not_overwrite_existing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ZOOPLA_SOURCE_USERNAME=env\nZOOPLA_SOURCE_PASSWORD=env\n", encoding="utf-8")
    store = CredentialStore(tmp_path / "credentials.enc")
    store.set("zoopla", "source", "kept", "kept")

    migrate_env_credentials(store, env_path=env)

    assert store.get("zoopla", "source") == ("kept", "kept")


def test_missing_env_is_noop(tmp_path):
    store = CredentialStore(tmp_path / "credentials.enc")
    migrate_env_credentials(store, env_path=tmp_path / "nope.env")
    assert store.has("zoopla", "source") is False
