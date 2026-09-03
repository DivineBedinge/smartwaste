from typing import Optional


def create_notification(
    conn,
    recipient_id: int,
    notification_type: str,
    title: str,
    content: str,
    link: Optional[str] = None,
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO notifications
            (recipient_id, notification_type, title, content, link)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (recipient_id, notification_type, title, content, link),
    )
    notification_id = cur.fetchone()[0]
    cur.close()
    return notification_id