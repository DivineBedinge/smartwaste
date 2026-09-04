import json
import re
from uuid import UUID
from typing import Any, Dict, Optional

from psycopg2.extras import Json

INTERNAL_LINK = re.compile(r"^/[a-zA-Z0-9/_-]+(?:#[a-zA-Z0-9_-]+)?$")


def validate_notification_link(link: Optional[str]) -> Optional[str]:
    if link is not None and not INTERNAL_LINK.fullmatch(link):
        raise ValueError("Le lien de notification doit être interne et lié à un rôle")
    return link


def create_notification(
    conn,
    recipient_id: int,
    notification_type: str,
    title: str,
    content: str,
    link: Optional[str] = None,
    translation_key: Optional[str] = None,
    translation_params: Optional[Dict[str, Any]] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    idempotency_key: Optional[UUID] = None,
) -> int:
    params = translation_params or {}
    if not isinstance(params, dict):
        raise TypeError("translation_params doit être un dictionnaire ou None")
    try:
        json.dumps(params, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("translation_params doit être sérialisable en JSON") from exc

    validate_notification_link(link)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO notifications
            (recipient_id, notification_type, title, content, link, translation_key,
             translation_params, resource_type, resource_id, idempotency_key)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (recipient_id, idempotency_key) WHERE idempotency_key IS NOT NULL
        DO UPDATE SET recipient_id = EXCLUDED.recipient_id
        RETURNING id
        """,
        (recipient_id, notification_type, title, content, link, translation_key, Json(params),
         resource_type, resource_id, str(idempotency_key) if idempotency_key else None),
    )
    notification_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO notification_delivery_outbox(notification_id, recipient_id)
           VALUES (%s, %s) ON CONFLICT (notification_id) DO NOTHING""",
        (notification_id, recipient_id),
    )
    cur.close()
    return notification_id


def pending_notification_events(conn, limit: int = 100) -> list[dict]:
    """Claim committed notification events; callers publish then acknowledge them."""
    cur = conn.cursor()
    cur.execute(
        """SELECT o.notification_id,o.recipient_id,n.notification_type,n.translation_key,
                  n.translation_params,n.resource_type,n.resource_id,n.created_at
           FROM notification_delivery_outbox o
           JOIN notifications n ON n.id=o.notification_id
           WHERE o.delivered_at IS NULL
           ORDER BY o.notification_id LIMIT %s FOR UPDATE OF o SKIP LOCKED""",
        (limit,),
    )
    columns = ("notification_id", "recipient_id", "type", "translation_key",
               "translation_params", "resource_type", "resource_id", "created_at")
    events = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    return events


def acknowledge_notification_event(conn, notification_id: int) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE notification_delivery_outbox SET delivered_at=NOW(), attempts=attempts+1 WHERE notification_id=%s AND delivered_at IS NULL",
        (notification_id,),
    )
    cur.close()


def record_notification_failure(conn, notification_id: int, error: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE notification_delivery_outbox SET attempts=attempts+1,last_error=%s WHERE notification_id=%s AND delivered_at IS NULL",
        (error[:500], notification_id),
    )
    cur.close()
