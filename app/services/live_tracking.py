import psycopg2
import psycopg2.extras
from database import get_db_connection

async def update_agent_position(agent_id: int, lat: float, lon: float):
    """Met à jour la position de l'agent dans une table dédiée."""
    conn = get_db_connection()
    cur = conn.cursor()
    # On suppose une table agent_positions (à créer)
    cur.execute("""
        INSERT INTO agent_positions (agent_id, lat, lon, timestamp)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (agent_id) DO UPDATE
        SET lat = EXCLUDED.lat, lon = EXCLUDED.lon, timestamp = NOW()
    """, (agent_id, lat, lon))
    conn.commit()
    cur.close()
    conn.close()

async def get_all_agent_positions():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT agent_id, lat, lon, timestamp FROM agent_positions")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows