import pytest

from relister.storage.property_images import PropertyImagesRepo


@pytest.fixture
def repo(tmp_path):
    return PropertyImagesRepo(tmp_path / "test.db")


def test_set_then_get(repo):
    repo.set_images_dir("123", "/imgs/a")
    assert repo.get_images_dir("123") == "/imgs/a"


def test_get_unknown_is_none(repo):
    assert repo.get_images_dir("nope") is None


def test_upsert_overwrites(repo):
    repo.set_images_dir("123", "/imgs/a")
    repo.set_images_dir("123", "/imgs/b")
    assert repo.get_images_dir("123") == "/imgs/b"


def test_migrate_moves_row(repo):
    repo.set_images_dir("old", "/imgs/a")
    repo.migrate_id("old", "new")
    assert repo.get_images_dir("old") is None
    assert repo.get_images_dir("new") == "/imgs/a"


def test_migrate_replaces_existing_new(repo):
    repo.set_images_dir("old", "/imgs/a")
    repo.set_images_dir("new", "/imgs/stale")
    repo.migrate_id("old", "new")
    assert repo.get_images_dir("new") == "/imgs/a"
    assert repo.get_images_dir("old") is None


def test_migrate_absent_old_is_noop(repo):
    repo.set_images_dir("new", "/imgs/keep")
    repo.migrate_id("missing", "new")
    assert repo.get_images_dir("new") == "/imgs/keep"
