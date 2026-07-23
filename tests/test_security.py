from relister.core.security import get_cipher, hash_name


def test_cipher_round_trips():
    cipher = get_cipher()
    token = cipher.encrypt(b"secret")
    assert cipher.decrypt(token) == b"secret"


def test_cipher_reuses_same_key():
    a = get_cipher()
    b = get_cipher()
    # A token from one cipher decrypts with the other -> same underlying key.
    assert b.decrypt(a.encrypt(b"x")) == b"x"


def test_hash_name_is_stable_hex_and_input_sensitive():
    first = hash_name("zoopla", "user@example.com")
    assert first == hash_name("zoopla", "user@example.com")
    assert all(c in "0123456789abcdef" for c in first)
    assert first != hash_name("zoopla", "other@example.com")
