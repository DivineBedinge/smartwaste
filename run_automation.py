"""Commande planifiable mono-instance pour les automatisations SmartWaste."""
from app.services.automation import run_daily_automation
from database import get_db_connection


if __name__ == "__main__":
    connection = get_db_connection()
    try:
        print(run_daily_automation(connection))
    finally:
        connection.close()
