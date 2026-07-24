import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from image_manager.image_manager_app import INSTRUCTIONS_FILENAME
from relister.gui.services.images_validator import validate_images_directory


def _img(path: Path) -> None:
    # is_supported_image / load_images only check the extension, not contents.
    path.write_bytes(b"fake-image-bytes")


def test_empty_text_is_neutral_ready():
    result = validate_images_directory("")
    assert result.state == "neutral"
    assert result.ready is True


def test_missing_directory_is_error(tmp_path):
    result = validate_images_directory(str(tmp_path / "does-not-exist"))
    assert result.state == "error"
    assert result.ready is False


def test_no_supported_images_is_warning(tmp_path):
    (tmp_path / "notes.txt").write_text("hi", encoding="utf-8")
    result = validate_images_directory(str(tmp_path))
    assert result.state == "warning"
    assert result.ready is False


def test_missing_instructions_is_warning_with_action(tmp_path):
    _img(tmp_path / "a.png")
    result = validate_images_directory(str(tmp_path))
    assert result.state == "warning"
    assert result.ready is False
    assert result.action_visible is True


def test_empty_instructions_is_warning(tmp_path):
    _img(tmp_path / "a.png")
    (tmp_path / INSTRUCTIONS_FILENAME).write_text("\n\n", encoding="utf-8")
    result = validate_images_directory(str(tmp_path))
    assert result.state == "warning"
    assert result.ready is False


def test_instructions_referencing_missing_file_is_warning(tmp_path):
    _img(tmp_path / "a.png")
    (tmp_path / INSTRUCTIONS_FILENAME).write_text("b.png\n", encoding="utf-8")
    result = validate_images_directory(str(tmp_path))
    assert result.state == "warning"
    assert result.ready is False


def test_valid_folder_is_success(tmp_path):
    _img(tmp_path / "a.png")
    (tmp_path / INSTRUCTIONS_FILENAME).write_text("a.png\n", encoding="utf-8")
    result = validate_images_directory(str(tmp_path))
    assert result.state == "success"
    assert result.ready is True
    assert "1 image " in result.message


def test_home_relative_path_is_expanded(tmp_path, monkeypatch):
    # A path stored as "~/pics" must resolve rather than read as non-existent.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows expanduser source
    _img(tmp_path / "a.png")
    (tmp_path / INSTRUCTIONS_FILENAME).write_text("a.png\n", encoding="utf-8")

    result = validate_images_directory("~")

    assert result.state == "success"
    assert result.ready is True
