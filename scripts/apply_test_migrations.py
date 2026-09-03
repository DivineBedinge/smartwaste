"""Apply only upward migrations to an explicitly named integration database."""
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database import require_test_database_url
from migrate_schema import apply_migrations


if __name__ == "__main__":
    connection = psycopg2.connect(require_test_database_url())
    try:
        print(f"Migrations appliquées: {apply_migrations(connection)}")
    finally:
        connection.close()
