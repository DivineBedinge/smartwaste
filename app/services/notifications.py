import json
from typing import Any, Dict, Optional

from psycopg2.extras import Json


def create_notification(
    conn,
    recipient_id: int,
    notification_type: str,
    title: str,
    content: str,
    link: Optional[str] = None,
    translation_key: Optional[str] = None,
    translation_params: Optional[Dict[str, Any]] = None,
) -> int:
    params = translation_params or {}
    if not isinstance(params, dict):
        raise TypeError("translation_params doit être un dictionnaire ou None")
    try:
        json.dumps(params, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("translation_params doit être sérialisable en JSON") from exc

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO notifications
            (recipient_id, notification_type, title, content, link, translation_key, translation_params)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (recipient_id, notification_type, title, content, link, translation_key, Json(params)),
    )
    notification_id = cur.fetchone()[0]
    cur.close()
    return notification_id
