import importlib

import relister.core.paths as paths


def test_data_dir_uses_app_name_and_exists():
    d = paths.data_dir()
    assert d.name == "AutoZoopla"
    assert d.is_dir()


def test_named_paths_live_under_data_dir():
    assert paths.database_path().name == "relister.db"
    assert paths.credentials_path().name == "credentials.enc"
    assert paths.database_path().parent == paths.data_dir()
    assert paths.browser_states_dir().parent == paths.data_dir()


def test_browser_cache_honours_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "pw"))
    importlib.reload(paths)
    assert paths.browser_cache_dir() == tmp_path / "pw"
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    importlib.reload(paths)
