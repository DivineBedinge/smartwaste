from pathlib import Path

from database import get_db_connection


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def apply_migrations() -> list[str]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute("SELECT filename FROM schema_migrations")
    applied = {row[0] for row in cur.fetchall()}
    applied_now = []
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if migration.name.endswith(".down.sql") or migration.name in applied:
            continue
        cur.execute(migration.read_text(encoding="utf-8"))
        cur.execute(
            "INSERT INTO schema_migrations (filename) VALUES (%s)",
            (migration.name,),
        )
        applied_now.append(migration.name)
    conn.commit()
    cur.close()
    conn.close()
    return applied_now


if __name__ == "__main__":
    print(f"Migrations appliquées: {apply_migrations()}")