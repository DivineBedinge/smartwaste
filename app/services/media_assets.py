from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.media_storage import MediaStorage, StoredMedia, get_media_storage


def insert_media_asset(conn, uploader_id: int, purpose: str, stored: StoredMedia,
                       resource_type: str | None = None, resource_id: int | None = None,
                       status: str = "temporary") -> str:
    asset_id = str(uuid4())
    retention = datetime.now(timezone.utc) + timedelta(hours=24) if status == "temporary" else None
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO media_assets
           (id,storage_key,uploader_id,purpose,resource_type,resource_id,mime_type,extension,
            size_bytes,width,height,sha256,status,retention_until)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (asset_id, stored.storage_key, uploader_id, purpose, resource_type, resource_id,
         stored.mime_type, stored.extension, stored.size_bytes, stored.width, stored.height,
         stored.sha256, status, retention),
    )
    cur.close()
    return asset_id


def store_media_with_compensation(conn, uploader_id: int, purpose: str, content: bytes,
                                  mime_type: str, resource_type: str | None = None,
                                  resource_id: int | None = None, status: str = "temporary",
                                  storage: MediaStorage | None = None) -> tuple[str, StoredMedia]:
    backend = storage or get_media_storage()
    stored = backend.save(content, mime_type)
    try:
        asset_id = insert_media_asset(conn, uploader_id, purpose, stored, resource_type, resource_id, status)
    except Exception:
        backend.delete(stored.storage_key)
        raise
    return asset_id, stored


def activate_media_asset(conn, asset_id: str, uploader_id: int, resource_type: str, resource_id: int) -> None:
    cur = conn.cursor()
    cur.execute(
        """UPDATE media_assets SET status='active',resource_type=%s,resource_id=%s,retention_until=NULL
           WHERE id=%s AND uploader_id=%s AND status='temporary' RETURNING id""",
        (resource_type, resource_id, asset_id, uploader_id),
    )
    if not cur.fetchone():
        cur.close()
        raise ValueError("Média temporaire introuvable ou non autorisé")
    cur.close()


def cleanup_temporary_media(conn, storage: MediaStorage | None = None, now: datetime | None = None) -> int:
    backend = storage or get_media_storage()
    cur = conn.cursor()
    cur.execute(
        """SELECT id,storage_key FROM media_assets
           WHERE status IN ('temporary','orphaned') AND retention_until < %s FOR UPDATE SKIP LOCKED""",
        (now or datetime.now(timezone.utc),),
    )
    rows = cur.fetchall()
    for asset_id, key in rows:
        backend.delete(key)
        cur.execute("UPDATE media_assets SET status='deleted',deleted_at=NOW() WHERE id=%s", (asset_id,))
    conn.commit()
    cur.close()
    return len(rows)
