"""Read-only private media integrity report. Never deletes files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.media_storage import validated_storage_root
from database import get_db_connection


def inspect_media(connection=None, root: Path | None = None) -> dict:
    storage_root = root or validated_storage_root()
    conn = connection or get_db_connection()
    owns = connection is None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT storage_key FROM media_assets WHERE status <> 'deleted' AND deleted_at IS NULL")
            referenced = {row[0] for row in cursor.fetchall()}
            cursor.execute("SELECT storage_key FROM media_assets WHERE status='temporary' AND created_at < NOW() - INTERVAL '24 hours'")
            expired_temporary = sorted(row[0] for row in cursor.fetchall())
        files = {item.name for item in storage_root.iterdir() if item.is_file() and not item.name.startswith(".upload-")} if storage_root.exists() else set()
        stale_uploads = sorted(item.name for item in storage_root.glob(".upload-*") if item.is_file()) if storage_root.exists() else []
        return {"missing_files": sorted(referenced - files), "orphan_files": sorted(files - referenced), "expired_temporary": expired_temporary, "stale_uploads": stale_uploads}
    finally:
        if owns:
            conn.close()


if __name__ == "__main__":
    print(json.dumps(inspect_media(), ensure_ascii=False))
