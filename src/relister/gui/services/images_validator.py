from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from image_manager.image_manager_app import (
    INSTRUCTIONS_FILENAME,
    is_supported_image,
    load_images,
)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validating a replacement-image folder.

    ``state`` is one of ``neutral`` / ``success`` / ``warning`` / ``error`` and
    maps directly to the image-status styling. ``ready`` gates the Start button.
    """

    state: str
    message: str
    ready: bool
    action_visible: bool = False


def validate_images_directory(images_text: str) -> ValidationResult:
    """Validate a replacement-image folder without touching any UI.

    Ported verbatim (branch for branch, message for message) from the former
    ``MainWindow._validate_images_directory`` so behaviour is unchanged; the
    caller renders the returned :class:`ValidationResult`.
    """

    images_text = images_text.strip()
    if not images_text:
        return ValidationResult(
            "neutral",
            "No replacement image folder selected. Existing scraped images will be used.",
            True,
        )

    images_path = Path(images_text)
    if not images_path.is_dir():
        return ValidationResult(
            "error",
            "The selected image folder does not exist. Choose a different folder.",
            False,
        )

    try:
        images = load_images(images_path)
    except OSError as exc:
        return ValidationResult(
            "error",
            f"The selected image folder could not be read: {exc}",
            False,
        )

    if not images:
        return ValidationResult(
            "warning",
            "No supported images were found in this folder. Select a different folder.",
            False,
        )

    instructions_path = images_path / INSTRUCTIONS_FILENAME
    if not instructions_path.is_file():
        return ValidationResult(
            "warning",
            f"{INSTRUCTIONS_FILENAME} is missing. Run the image organiser before continuing.",
            False,
            True,
        )

    try:
        ordered_names = [
            line.strip()
            for line in instructions_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as exc:
        return ValidationResult(
            "error",
            f"{INSTRUCTIONS_FILENAME} could not be read: {exc}",
            False,
            True,
        )

    if not ordered_names:
        return ValidationResult(
            "warning",
            f"{INSTRUCTIONS_FILENAME} is empty. Open the image organiser and save at least one visible image.",
            False,
            True,
        )

    missing = [
        name for name in ordered_names if not is_supported_image(images_path / name)
    ]
    if missing:
        preview = ", ".join(missing[:3])
        suffix = "…" if len(missing) > 3 else ""
        return ValidationResult(
            "warning",
            f"The saved order refers to missing or unsupported files: {preview}{suffix}. Re-save the image order.",
            False,
            True,
        )

    count = len(ordered_names)
    return ValidationResult(
        "success",
        f"Image folder ready: {count} image{'s' if count != 1 else ''} will be uploaded in the saved order.",
        True,
    )
