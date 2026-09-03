import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import os
from typing import Optional
from urllib.parse import urlparse

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL doit être défini dans l'environnement")

def get_db_connection():
    """Crée une connexion PostgreSQL."""
    return psycopg2.connect(DATABASE_URL)


def require_test_database_url(database_url: Optional[str] = None) -> str:
    """Reject destructive test setup unless the target database is explicit."""
    value = database_url or os.getenv("TEST_DATABASE_URL")
    if not value:
        raise RuntimeError("TEST_DATABASE_URL doit être défini")
    database_name = urlparse(value).path.lstrip("/").split("?", 1)[0]
    if "_test" not in database_name.lower():
        raise RuntimeError("Refus de toucher une base dont le nom ne contient pas '_test'")
    if database_name.lower() == "smartwaste_db":
        raise RuntimeError("La base personnelle smartwaste_db est interdite aux tests")
    return value

