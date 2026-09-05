"""Mesure locale bornee et en lecture seule de la couche PostgreSQL/PostGIS."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database import require_test_database_url


def measure() -> dict:
    url = require_test_database_url(os.environ.get("DATABASE_URL"))
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(),PostGIS_Version(),pg_database_size(current_database())")
            database, postgis, size = cur.fetchone()
            started = time.perf_counter()
            cur.execute("SELECT id,status FROM reports ORDER BY id LIMIT 50")
            page_rows = len(cur.fetchall())
            page_ms = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            cur.execute(
                """SELECT COUNT(*) FROM reports
                   WHERE ST_DWithin(geometry::geography,
                     ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)""",
                (9.7, 4.05, 10_000),
            )
            near = cur.fetchone()[0]
            geo_ms = (time.perf_counter() - started) * 1000
            cur.execute("SELECT COUNT(*) FROM reports")
            reports = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM users")
            users = cur.fetchone()[0]
        return {
            "database": database,
            "postgis": postgis,
            "database_bytes": size,
            "reports": reports,
            "users": users,
            "page_limit": 50,
            "page_rows": page_rows,
            "page_query_ms": round(page_ms, 3),
            "geo_radius_m": 10_000,
            "geo_matches": near,
            "geo_query_ms": round(geo_ms, 3),
            "warning": "Mesure locale synthetique; aucune extrapolation industrielle",
        }
    finally:
        conn.close()


if __name__ == "__main__":
    print(json.dumps(measure(), ensure_ascii=False, indent=2))
