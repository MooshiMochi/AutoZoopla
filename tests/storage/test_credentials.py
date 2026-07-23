from relister.storage.credentials import CredentialStore


def test_set_get_round_trip(tmp_path):
    store = CredentialStore(tmp_path / "credentials.enc")
    store.set("zoopla", "source", "user@example.com", "s3cret")
    assert store.get("zoopla", "source") == ("user@example.com", "s3cret")


def test_has_reflects_presence(tmp_path):
    store = CredentialStore(tmp_path / "credentials.enc")
    assert store.has("zoopla", "destination") is False
    store.set("zoopla", "destination", "u", "p")
    assert store.has("zoopla", "destination") is True


def test_unknown_returns_none(tmp_path):
    store = CredentialStore(tmp_path / "credentials.enc")
    assert store.get("zoopla", "source") is None


def test_file_is_not_plaintext(tmp_path):
    path = tmp_path / "credentials.enc"
    store = CredentialStore(path)
    store.set("zoopla", "source", "user@example.com", "s3cret-password")
    blob = path.read_bytes()
    assert b"s3cret-password" not in blob
    assert b"user@example.com" not in blob
