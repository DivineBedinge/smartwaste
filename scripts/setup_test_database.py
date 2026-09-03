"""Bootstrap the isolated integration database from test.sql and migrations."""
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database import require_test_database_url
from migrate_schema import apply_migrations


def setup_test_database() -> None:
    url = require_test_database_url()
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute((ROOT / "test.sql").read_text(encoding="utf-8"))
        connection.commit()
        apply_migrations(connection)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    setup_test_database()
    print("Base d'intégration initialisée")
