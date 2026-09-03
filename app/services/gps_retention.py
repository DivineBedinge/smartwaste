import os


GPS_RETENTION_DAYS = int(os.getenv("GPS_RETENTION_DAYS", "30"))


def purge_old_positions(conn, retention_days: int = GPS_RETENTION_DAYS) -> int:
    if retention_days < 1:
        raise ValueError("La rétention GPS doit être positive")
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM agent_positions WHERE timestamp < NOW() - (%s * INTERVAL '1 day')",
        (retention_days,),
    )
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    return deleted