from relister.storage.app_settings import AppSettings


def test_set_get_round_trip(tmp_path):
    settings = AppSettings(tmp_path / "settings.json")
    settings.set("zoopla_branch_id", "12345")
    assert settings.get("zoopla_branch_id") == "12345"


def test_missing_key_returns_default(tmp_path):
    settings = AppSettings(tmp_path / "settings.json")
    assert settings.get("nope") is None
    assert settings.get("nope", "fallback") == "fallback"


def test_persists_across_instances(tmp_path):
    path = tmp_path / "settings.json"
    AppSettings(path).set("zoopla_branch_id", "999")
    assert AppSettings(path).get("zoopla_branch_id") == "999"
