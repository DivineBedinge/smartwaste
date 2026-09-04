from __future__ import annotations

import os
from datetime import date, timedelta
from uuid import NAMESPACE_URL, uuid5

from psycopg2.extras import Json

from app.services.collections import generate_database_occurrences
from app.services.gps_retention import purge_old_positions
from app.services.media_assets import cleanup_temporary_media
from app.services.notifications import create_notification


def run_daily_automation(conn, run_date: date | None = None) -> dict:
    day = run_date or date.today()
    key = f"daily:{day.isoformat()}"
    cur = conn.cursor()
    # A session lock survives the commits performed by the occurrence generator.
    cur.execute("SELECT pg_try_advisory_lock(hashtext('smartwaste_daily_automation'))")
    if not cur.fetchone()[0]:
        cur.close(); return {"status": "locked"}
    cur.execute("""INSERT INTO job_runs(job_name,idempotency_key,status) VALUES ('daily',%s,'running')
        ON CONFLICT(idempotency_key) DO UPDATE SET status='running',result='{}'::jsonb,started_at=NOW(),finished_at=NULL
        WHERE job_runs.status='failed' RETURNING id""",(key,))
    row=cur.fetchone()
    if not row:
        cur.execute("SELECT pg_advisory_unlock(hashtext('smartwaste_daily_automation'))")
        cur.close();return {"status":"already_completed"}
    run_id=row[0];conn.commit()
    result={}
    try:
        horizon=int(os.getenv("COLLECTION_GENERATION_HORIZON_DAYS","30"))
        result["occurrences_created"]=generate_database_occurrences(conn,day,day+timedelta(days=horizon))
        cur=conn.cursor();cur.execute("""UPDATE collection_occurrences o SET status='refusee',refusal_reason='response_timeout',collector_id=NULL,updated_at=NOW()
            FROM domestic_subscriptions s WHERE o.subscription_id=s.id AND o.status='proposee' AND o.response_due_at<NOW()
            RETURNING o.id,s.user_id""");expired=cur.fetchall();result["proposals_expired"]=len(expired)
        for occurrence_id,citizen_id in expired:
            create_notification(conn,citizen_id,"collection_proposal_expired","Proposition expirée",f"La proposition de collecte #{occurrence_id} a expiré.",f"/citoyen#collecte-{occurrence_id}","notification.collection_proposal_expired",{"collection_id":occurrence_id},resource_type="collection",resource_id=occurrence_id,idempotency_key=uuid5(NAMESPACE_URL,f"smartwaste:proposal-expired:{occurrence_id}"))
        cur.execute("""UPDATE collection_occurrences o SET status='manquee',missed_reason='overdue',updated_at=NOW()
            FROM domestic_subscriptions s WHERE o.subscription_id=s.id AND o.scheduled_for<NOW() AND o.status IN ('programmee','acceptee','en_route','arrivee')
            RETURNING o.id,s.user_id""");overdue=cur.fetchall();result["overdue_marked"]=len(overdue)
        for occurrence_id,citizen_id in overdue:
            create_notification(conn,citizen_id,"collection_overdue","Collecte manquée",f"La collecte #{occurrence_id} est arrivée à échéance.",f"/citoyen#collecte-{occurrence_id}","notification.collection_overdue",{"collection_id":occurrence_id},resource_type="collection",resource_id=occurrence_id,idempotency_key=uuid5(NAMESPACE_URL,f"smartwaste:collection-overdue:{occurrence_id}"))
        cur.execute("""UPDATE collection_occurrences o SET status='confirmee',confirmed_at=NOW(),updated_at=NOW()
            FROM domestic_subscriptions s WHERE o.subscription_id=s.id AND o.status='en_attente_confirmation' AND o.confirmation_due_at<NOW()
            RETURNING o.id,s.user_id""");auto_confirmed=cur.fetchall();result["collections_auto_confirmed"]=len(auto_confirmed)
        for occurrence_id,citizen_id in auto_confirmed:
            cur.execute("INSERT INTO collection_transition_history(occurrence_id,actor_role,from_status,to_status,reason) VALUES (%s,'system','en_attente_confirmation','confirmee','confirmation_timeout')",(occurrence_id,))
            create_notification(conn,citizen_id,"collection_auto_confirmed","Collecte confirmée automatiquement",f"La collecte #{occurrence_id} a été confirmée à l’expiration du délai.",f"/citoyen#collecte-{occurrence_id}","notification.collection_auto_confirmed",{"collection_id":occurrence_id},resource_type="collection",resource_id=occurrence_id,idempotency_key=uuid5(NAMESPACE_URL,f"smartwaste:collection-auto-confirmed:{occurrence_id}"))
        retention=int(os.getenv("NOTIFICATION_RETENTION_DAYS","365"));cur.execute("DELETE FROM notifications WHERE is_read=TRUE AND created_at<NOW()-(%s||' days')::interval",(retention,));result["notifications_deleted"]=cur.rowcount;conn.commit();cur.close()
        result["temporary_media_deleted"]=cleanup_temporary_media(conn)
        result["gps_positions_deleted"]=purge_old_positions(conn)
        cur=conn.cursor();cur.execute("UPDATE job_runs SET status='completed',result=%s,finished_at=NOW() WHERE id=%s",(Json(result),run_id));conn.commit()
        cur.execute("SELECT pg_advisory_unlock(hashtext('smartwaste_daily_automation'))");cur.close();return {"status":"completed",**result}
    except Exception as error:
        conn.rollback();cur=conn.cursor();cur.execute("UPDATE job_runs SET status='failed',result=%s,finished_at=NOW() WHERE id=%s",(Json({"error":str(error)[:500]}),run_id));conn.commit();cur.execute("SELECT pg_advisory_unlock(hashtext('smartwaste_daily_automation'))");cur.close();raise
