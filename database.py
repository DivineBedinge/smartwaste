import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL doit être défini dans l'environnement")

def get_db_connection():
    """Crée une connexion PostgreSQL."""
    return psycopg2.connect(DATABASE_URL)

