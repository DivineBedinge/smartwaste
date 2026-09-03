from database import get_db_connection
import psycopg2.extras

conn = get_db_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Pour chaque signalement sans groupe, lui assigner un groupe
cur.execute("SELECT id, geometry, waste_type FROM reports WHERE duplicate_group_id IS NULL")
reports = cur.fetchall()

for r in reports:
    # Chercher un groupe existant dans un rayon de 50m avec même waste_type
    cur.execute("""
        SELECT duplicate_group_id
        FROM reports
        WHERE id != %s
          AND waste_type = %s
          AND ST_DWithin(geometry, ST_SetSRID(%s, 4326), 0.00045)  -- ~50m
          AND duplicate_group_id IS NOT NULL
        LIMIT 1
    """, (r['id'], r['waste_type'], r['geometry']))
    row = cur.fetchone()
    if row:
        group_id = row['duplicate_group_id']
        cur.execute("""
            UPDATE reports
            SET duplicate_group_id = %s, is_primary = FALSE
            WHERE id = %s
        """, (group_id, r['id']))
    else:
        # Nouveau groupe
        cur.execute("""
            UPDATE reports
            SET duplicate_group_id = %s, is_primary = TRUE, report_count = 1
            WHERE id = %s
        """, (r['id'], r['id']))

conn.commit()
cur.close()
conn.close()
print("Migration terminée.")