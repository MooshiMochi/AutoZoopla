from __future__ import annotations

import sqlite3
from pathlib import Path

from relister.core.paths import database_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS property_images (
    listing_id TEXT PRIMARY KEY,
    images_dir TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    # Default (rollback) journal mode: no -wal/-shm side files, most portable
    # for a tiny single-user database.
    return sqlite3.connect(path or database_path())


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
