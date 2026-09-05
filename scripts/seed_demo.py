"""Jeu fictif idempotent, refuse sur toute base non demo/test."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.security import hash_password
from database import get_db_connection


EMAILS = {
    "citoyen": "citoyen.demo@smartwaste.invalid",
    "agent": "agent.demo@smartwaste.invalid",
    "ramasseur": "ramasseur.demo@smartwaste.invalid",
    "gestionnaire": "gestionnaire.demo@smartwaste.invalid",
}
CLIENT_ID = UUID("00000000-0000-4000-8000-000000000701")


def require_safe_target(url: str) -> str:
    name = urlparse(url).path.lstrip("/").split("?", 1)[0].lower()
    if "_test" not in name and "demo" not in name:
        raise RuntimeError("Le seed est limite a une base demo ou _test")
    if name == "smartwaste_db":
        raise RuntimeError("smartwaste_db est interdite")
    return name


def required_passwords() -> dict[str, str]:
    values = {role: os.getenv(f"DEMO_{role.upper()}_PASSWORD", "") for role in EMAILS}
    if any(len(value) < 12 for value in values.values()):
        raise RuntimeError("Les quatre DEMO_<ROLE>_PASSWORD (12 caracteres minimum) sont obligatoires")
    return values


def seed(conn, passwords: dict[str, str]) -> dict:
    cur = conn.cursor()
    ids = {}
    for role, email in EMAILS.items():
        cur.execute(
            """INSERT INTO users(email,password_hash,role,arrondissement,service_area)
               VALUES (%s,%s,%s,'Douala 1','demo-douala-1')
               ON CONFLICT(email) DO UPDATE SET active=TRUE
               RETURNING id""",
            (email, hash_password(passwords[role]), role),
        )
        ids[role] = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO zones(nom,zone_type,arrondissement,geometry)
           SELECT 'Zone demonstration Douala 1','operationnelle','Douala 1',
             ST_GeomFromText('POLYGON((9.68 4.02,9.75 4.02,9.75 4.08,9.68 4.08,9.68 4.02))',4326)
           WHERE NOT EXISTS(SELECT 1 FROM zones WHERE nom='Zone demonstration Douala 1')
           RETURNING id"""
    )
    zone_row = cur.fetchone()
    if zone_row:
        zone_id = zone_row[0]
    else:
        cur.execute("SELECT id FROM zones WHERE nom='Zone demonstration Douala 1'")
        zone_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO reports(user_id,agent_id,geometry,severity,confidence,status,waste_type,
                   client_id,description,address_text,classification_source,human_review_required)
           VALUES (%s,%s,ST_SetSRID(ST_MakePoint(9.7043,4.0511),4326),'moderee',NULL,
                   'assigne','plastique',%s,'Donnee fictive de soutenance','Douala 1, adresse fictive',
                   'indisponible',TRUE)
           ON CONFLICT DO NOTHING
           RETURNING id""",
        (ids["citoyen"], ids["agent"], str(CLIENT_ID)),
    )
    report_row = cur.fetchone()
    if report_row:
        report_id = report_row[0]
    else:
        cur.execute("SELECT id FROM reports WHERE user_id=%s AND client_id=%s", (ids["citoyen"], str(CLIENT_ID)))
        report_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO report_disputes(report_id,citizen_id,reason,comment,status)
           SELECT %s,%s,'preuve_contestee','Contestation fictive pour demonstration','soumise'
           WHERE NOT EXISTS(SELECT 1 FROM report_disputes WHERE report_id=%s AND citizen_id=%s)""",
        (report_id, ids["citoyen"], report_id, ids["citoyen"]),
    )
    cur.execute(
        """INSERT INTO subscription_plans(name,frequency,price,service_area)
           SELECT 'Plan demonstration','hebdomadaire',0,'demo-douala-1'
           WHERE NOT EXISTS(SELECT 1 FROM subscription_plans WHERE name='Plan demonstration')"""
    )
    cur.execute("SELECT id FROM subscription_plans WHERE name='Plan demonstration'")
    plan_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO domestic_subscriptions(user_id,plan_id,address_geometry,address_text,service_area,status)
           SELECT %s,%s,ST_SetSRID(ST_MakePoint(9.705,4.052),4326),'Adresse fictive demo','demo-douala-1','active'
           WHERE NOT EXISTS(SELECT 1 FROM domestic_subscriptions WHERE user_id=%s AND status='active')
           RETURNING id""",
        (ids["citoyen"], plan_id, ids["citoyen"]),
    )
    subscription_row = cur.fetchone()
    if subscription_row:
        subscription_id = subscription_row[0]
    else:
        cur.execute("SELECT id FROM domestic_subscriptions WHERE user_id=%s AND status='active' ORDER BY id LIMIT 1", (ids["citoyen"],))
        subscription_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO collection_occurrences(subscription_id,collector_id,scheduled_for,status)
           VALUES (%s,%s,date_trunc('day',NOW())+INTERVAL '1 day 9 hours','acceptee')
           ON CONFLICT(subscription_id,scheduled_for) DO UPDATE SET collector_id=EXCLUDED.collector_id
           RETURNING id""",
        (subscription_id, ids["ramasseur"]),
    )
    occurrence_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO tours(collector_id,zone_id,planned_date,status,tour_type,routing_status,created_by)
           SELECT %s,%s,CURRENT_DATE,'planifiee','collection','unavailable',%s
           WHERE NOT EXISTS(SELECT 1 FROM tours WHERE collector_id=%s AND planned_date=CURRENT_DATE AND tour_type='collection')
           RETURNING id""",
        (ids["ramasseur"], zone_id, ids["gestionnaire"], ids["ramasseur"]),
    )
    tour_row = cur.fetchone()
    if tour_row:
        tour_id = tour_row[0]
    else:
        cur.execute("SELECT id FROM tours WHERE collector_id=%s AND planned_date=CURRENT_DATE AND tour_type='collection' ORDER BY id LIMIT 1", (ids["ramasseur"],))
        tour_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO tour_stops(tour_id,occurrence_id,stop_order,geometry)
           SELECT %s,%s,1,ST_SetSRID(ST_MakePoint(9.705,4.052),4326)
           WHERE NOT EXISTS(SELECT 1 FROM tour_stops WHERE tour_id=%s AND occurrence_id=%s)""",
        (tour_id, occurrence_id, tour_id, occurrence_id),
    )
    cur.execute(
        """INSERT INTO operational_positions(tour_id,actor_id,actor_role,geometry,accuracy_m,source,expires_at)
           SELECT %s,%s,'ramasseur',ST_SetSRID(ST_MakePoint(9.703,4.050),4326),25,'demo',NOW()+INTERVAL '30 minutes'
           WHERE NOT EXISTS(SELECT 1 FROM operational_positions WHERE tour_id=%s AND actor_id=%s AND expires_at>NOW())""",
        (tour_id, ids["ramasseur"], tour_id, ids["ramasseur"]),
    )
    cur.execute(
        """INSERT INTO conversations(resource_type,resource_id,created_by)
           VALUES ('report',%s,%s) ON CONFLICT(resource_type,resource_id) DO UPDATE SET status='open'
           RETURNING id""",
        (report_id, ids["citoyen"]),
    )
    conversation_id = cur.fetchone()[0]
    for user_id in (ids["citoyen"], ids["agent"], ids["gestionnaire"]):
        cur.execute("INSERT INTO conversation_participants(conversation_id,user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (conversation_id, user_id))
    cur.execute(
        """INSERT INTO notifications(recipient_id,notification_type,title,content,translation_key,translation_params,resource_type,resource_id)
           SELECT %s,'demo_ready','Demonstration prete','Donnees fictives chargees','demo.ready','{}','report',%s
           WHERE NOT EXISTS(SELECT 1 FROM notifications WHERE recipient_id=%s AND notification_type='demo_ready' AND resource_id=%s)""",
        (ids["citoyen"], report_id, ids["citoyen"], report_id),
    )
    conn.commit()
    cur.close()
    return {"database": "authorized", "users": EMAILS, "report_id": report_id, "occurrence_id": occurrence_id, "tour_id": tour_id, "zone_id": zone_id}


def main() -> int:
    url = os.getenv("DATABASE_URL", "")
    require_safe_target(url)
    passwords = required_passwords()
    conn = get_db_connection()
    try:
        print(json.dumps(seed(conn, passwords), ensure_ascii=False, indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
