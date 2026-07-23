from __future__ import annotations

from image_manager.image_manager_app import ImageOrderPage


class ImagePage(ImageOrderPage):
    """The image organiser as a registrable workspace page.

    Subclasses :class:`ImageOrderPage` so it keeps every existing signal
    (``instructions_saved`` / ``directory_changed``) and method
    (``load_directory`` / ``choose_directory`` / ``shutdown``) unchanged; it only
    adds the page metadata the navigation registry needs.
    """

    nav_label = "Image organiser"

    def on_activated(self) -> None:
        return None
