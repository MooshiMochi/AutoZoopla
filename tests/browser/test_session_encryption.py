import json

from relister.browser.session import load_state, save_state, session_filename


def test_session_filename_is_opaque_and_enc(tmp_path):
    name = session_filename("zoopla", "user@example.com")
    assert name.endswith(".enc")
    assert "user@example.com" not in name
    assert name == session_filename("zoopla", "user@example.com")


def test_state_round_trips(tmp_path):
    path = tmp_path / "sess.enc"
    state = {"cookies": [{"name": "sid", "value": "abc"}], "origins": []}
    save_state(path, state)
    assert load_state(path) == state


def test_stored_state_is_not_plaintext(tmp_path):
    path = tmp_path / "sess.enc"
    save_state(path, {"cookies": [{"name": "sid", "value": "topsecret"}]})
    blob = path.read_bytes()
    assert b"topsecret" not in blob
    assert b"cookies" not in blob


def test_missing_file_returns_none(tmp_path):
    assert load_state(tmp_path / "absent.enc") is None


def test_garbage_file_returns_none(tmp_path):
    path = tmp_path / "sess.enc"
    path.write_bytes(b"not a valid fernet token")
    assert load_state(path) is None
