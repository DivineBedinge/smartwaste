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
    cur.close()
    return notification_id
