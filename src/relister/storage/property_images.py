from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .database import connect, init_schema


class PropertyImagesRepo:
    """Persists the mapping of a listing ID to its images folder.

    Each method opens a short-lived connection; all access is expected on the
    GUI thread (the relist worker never touches the database).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path
        with connect(self._db_path) as conn:
            init_schema(conn)

    def get_images_dir(self, listing_id: str) -> str | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT images_dir FROM property_images WHERE listing_id = ?",
                (listing_id,),
            ).fetchone()
        return row[0] if row else None

    def set_images_dir(self, listing_id: str, images_dir: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO property_images(listing_id, images_dir, updated_at) "
                "VALUES(?, ?, ?) ON CONFLICT(listing_id) DO UPDATE SET "
                "images_dir = excluded.images_dir, updated_at = excluded.updated_at",
                (listing_id, images_dir, now),
            )
            conn.commit()

    def migrate_id(self, old_id: str, new_id: str) -> None:
        """Move a saved folder from ``old_id`` to ``new_id`` after a relist.

        No-op if ``old_id`` has no row; replaces any existing ``new_id`` row.
        """

        if old_id == new_id:
            return
        now = datetime.now(timezone.utc).isoformat()
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT images_dir FROM property_images WHERE listing_id = ?",
                (old_id,),
            ).fetchone()
            if row is None:
                return
            conn.execute("DELETE FROM property_images WHERE listing_id = ?", (new_id,))
            conn.execute(
                "UPDATE property_images SET listing_id = ?, updated_at = ? "
                "WHERE listing_id = ?",
                (new_id, now, old_id),
            )
            conn.commit()
