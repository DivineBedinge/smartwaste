from pathlib import Path
import hashlib

from database import get_db_connection


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def apply_migrations(connection=None) -> list[str]:
    conn = connection or get_db_connection()
    owns_connection = connection is None
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename VARCHAR(255) PRIMARY KEY,
            checksum CHAR(64),
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute("ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS checksum CHAR(64)")
    conn.commit()
    cur.execute("SELECT filename, checksum FROM schema_migrations")
    applied = {row[0]: row[1] for row in cur.fetchall()}
    applied_now = []
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if migration.name.endswith(".down.sql"):
            continue
        content = migration.read_text(encoding="utf-8")
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if migration.name in applied:
            recorded = applied[migration.name]
            if recorded is not None and recorded != checksum:
                raise RuntimeError(f"Migration modifiée après application: {migration.name}")
            if recorded is None:
                cur.execute("UPDATE schema_migrations SET checksum=%s WHERE filename=%s", (checksum, migration.name))
                conn.commit()
            continue
        try:
            cur.execute(content)
            cur.execute(
                "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                (migration.name, checksum),
            )
            conn.commit()
            applied_now.append(migration.name)
        except Exception:
            conn.rollback()
            raise
    cur.close()
    if owns_connection:
        conn.close()
    return applied_now


if __name__ == "__main__":
    print(f"Migrations appliquées: {apply_migrations()}")
