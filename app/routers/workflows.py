from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from psycopg2.extras import Json

from core.policy import COLLECTION_TRANSITIONS, can_transition, is_manager_role
from app.services.collections import generate_database_occurrences
from app.services.gps_retention import purge_old_positions
from app.services.notifications import create_notification
from app.services.media_assets import store_media_with_compensation
from app.services.media_storage import get_media_storage
from app.services.uploads import read_validated_image
from core.security import decode_token
from database import get_db_connection


router = APIRouter(prefix="/api/v1", tags=["workflows"])
security = HTTPBearer()


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide ou expiré")
    return payload


def require_citizen(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "citoyen":
        raise HTTPException(403, "Réservé aux citoyens")
    return user


def require_collector(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "ramasseur":
        raise HTTPException(403, "Réservé aux ramasseurs privés")
    return user


def require_manager(user: dict = Depends(current_user)) -> dict:
    if not is_manager_role(user.get("role", "")):
        raise HTTPException(403, "Réservé aux gestionnaires")
    return user


class SubscriptionCreate(BaseModel):
    plan_id: Optional[int] = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    service_area: Optional[str] = Field(default=None, max_length=120)
    preferred_slot_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class SubscriptionStatusUpdate(BaseModel):
    status: str


class SupportRequestCreate(BaseModel):
    category: str = Field(min_length=2, max_length=64)
    subject: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2, max_length=10000)
    priority: str = "normal"
    attachment_url: Optional[str] = Field(default=None, max_length=2048)
    resource_type: Optional[str] = None
    resource_id: Optional[int] = Field(default=None, ge=1)


class CollectionStatusUpdate(BaseModel):
    status: str
    missed_reason: Optional[str] = Field(default=None, max_length=64)
    comment: Optional[str] = Field(default=None, max_length=1000)


class CollectorAssignment(BaseModel):
    collector_id: int
    reason: Optional[str] = Field(default=None, max_length=1000)


class CollectorProposalResponse(BaseModel):
    accept: bool
    reason: Optional[str] = Field(default=None, max_length=500)


class CitizenCollectionDecision(BaseModel):
    confirm: bool
    reason: Optional[str] = Field(default=None, max_length=1000)


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    frequency: str
    price: float = Field(ge=0)
    service_area: Optional[str] = Field(default=None, max_length=120)


class ProfessionalStatusUpdate(BaseModel):
    active: bool


class OccurrenceGenerationRequest(BaseModel):
    start: str
    until: str


class CollectionScheduleUpdate(BaseModel):
    scheduled_for: datetime


class SupportResponseUpdate(BaseModel):
    response: str = Field(min_length=1, max_length=10000)


class SupportStatusUpdate(BaseModel):
    status: str


SUPPORT_CATEGORIES = {"collecte_manquee", "comportement", "erreur_affectation", "adresse_inaccessible", "danger", "panne", "preuve_contestee", "probleme_technique", "suggestion", "autre"}
SUPPORT_STATUSES = {"soumise", "en_examen", "reponse_envoyee", "resolue", "rouverte", "cloturee"}
RESOURCE_TYPES = {"report", "tour", "collection", "subscription", "conversation", "general"}


def validate_support_resource(cur, resource_type, resource_id, user):
    if resource_type in {None, "general"}:
        if resource_id is not None:
            raise HTTPException(422, "Une demande générale ne doit pas avoir d'identifiant de ressource")
        return
    if resource_id is None:
        raise HTTPException(422, "Identifiant de ressource obligatoire")
    if is_manager_role(user.get("role", "")):
        return
    queries = {
        "report": "SELECT 1 FROM reports WHERE id=%s AND (user_id=%s OR agent_id=%s)",
        "tour": "SELECT 1 FROM tours WHERE id=%s AND agent_id=%s",
        "collection": "SELECT 1 FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE o.id=%s AND (s.user_id=%s OR o.collector_id=%s)",
        "subscription": "SELECT 1 FROM domestic_subscriptions WHERE id=%s AND user_id=%s",
        "conversation": "SELECT 1 FROM conversation_participants WHERE conversation_id=%s AND user_id=%s",
    }
    query = queries[resource_type]
    params = (resource_id, user["user_id"], user["user_id"]) if resource_type in {"report", "collection"} else (resource_id, user["user_id"])
    cur.execute(query, params)
    if not cur.fetchone():
        raise HTTPException(403, "Accès refusé à cette ressource")


def role_home(role: str) -> str:
    return "gestionnaire" if is_manager_role(role) else role


def notify_collection(conn, recipient_id: int, occurrence_id: int, event: str, title: str, content: str, **params):
    return create_notification(
        conn,
        recipient_id,
        event,
        title,
        content,
        f"/ramasseur#collecte-{occurrence_id}",
        f"notification.{event}",
        {"collection_id": occurrence_id, **params},
    )


@router.post("/abonnements-domestiques")
def create_domestic_subscription(
    payload: SubscriptionCreate,
    user: dict = Depends(require_citizen),
):
    conn = get_db_connection()
    cur = conn.cursor()
    if payload.plan_id is not None:
        cur.execute("SELECT 1 FROM subscription_plans WHERE id=%s AND active=TRUE",(payload.plan_id,))
        if not cur.fetchone(): cur.close();conn.close();raise HTTPException(422,"Plan actif introuvable")
    if payload.preferred_slot_id is not None:
        cur.execute("SELECT 1 FROM service_slots WHERE id=%s AND active=TRUE AND (%s IS NULL OR service_area=%s)",(payload.preferred_slot_id,payload.service_area,payload.service_area))
        if not cur.fetchone(): cur.close();conn.close();raise HTTPException(422,"Créneau invalide pour cette zone")
    cur.execute("SELECT 1 FROM domestic_subscriptions WHERE user_id=%s AND status IN ('active','suspended') AND (%s IS NULL OR plan_id=%s)",(user["user_id"],payload.plan_id,payload.plan_id))
    if cur.fetchone(): cur.close();conn.close();raise HTTPException(409,"Abonnement incompatible déjà existant")
    cur.execute(
        """
        INSERT INTO domestic_subscriptions
            (user_id, plan_id, address_geometry, service_area, preferred_slot_id, notes)
        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)
        RETURNING id, status, created_at
        """,
        (
            user["user_id"], payload.plan_id, payload.lon, payload.lat,
            payload.service_area, payload.preferred_slot_id, payload.notes,
        ),
    )
    result = cur.fetchone()
    create_notification(
        conn, user["user_id"], "subscription_created", "Abonnement créé",
        "Votre abonnement de collecte domestique a été créé.",
        f"/citoyen#abonnement-{result[0]}", "notification.subscription_created",
        {"subscription_id": result[0]}, resource_type="subscription", resource_id=result[0],
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"id": result[0], "status": result[1], "created_at": result[2]}


@router.get("/abonnements-domestiques/mes-abonnements")
def list_my_subscriptions(user: dict = Depends(require_citizen)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, plan_id, service_area, preferred_slot_id, status, notes,
               ST_Y(address_geometry) AS lat, ST_X(address_geometry) AS lon,
               created_at, updated_at
        FROM domestic_subscriptions
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
        (user["user_id"],),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.patch("/abonnements-domestiques/{subscription_id}/status")
def update_my_subscription(
    subscription_id: int,
    payload: SubscriptionStatusUpdate,
    user: dict = Depends(require_citizen),
):
    if payload.status not in {"active", "suspended", "cancelled"}:
        raise HTTPException(400, "Statut d'abonnement invalide")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE domestic_subscriptions
        SET status = %s, updated_at = NOW()
        WHERE id = %s AND user_id = %s
        RETURNING id, status
        """,
        (payload.status, subscription_id, user["user_id"]),
    )
    result = cur.fetchone()
    if result:
        create_notification(
            conn, user["user_id"], "subscription_updated", "Abonnement mis à jour",
            "Votre abonnement de collecte domestique a été mis à jour.",
            f"/citoyen#abonnement-{result[0]}", "notification.subscription_updated",
            {"subscription_id": result[0], "status": result[1]},
            resource_type="subscription", resource_id=result[0],
        )
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Abonnement non trouvé")
    return {"id": result[0], "status": result[1]}


@router.post("/demandes-support")
def create_support_request(
    payload: SupportRequestCreate,
    user: dict = Depends(current_user),
):
    if payload.priority not in {"basse", "normal", "haute", "critique"}:
        raise HTTPException(400, "Priorité invalide")
    if payload.category not in SUPPORT_CATEGORIES:
        raise HTTPException(422, "Catégorie invalide")
    if payload.resource_type and payload.resource_type not in RESOURCE_TYPES:
        raise HTTPException(422, "Type de ressource invalide")
    if payload.attachment_url:
        raise HTTPException(422, "Les pièces jointes doivent utiliser le service d'upload sécurisé")
    conn = get_db_connection()
    cur = conn.cursor()
    validate_support_resource(cur, payload.resource_type, payload.resource_id, user)
    cur.execute(
        """
        INSERT INTO support_requests
            (author_id, author_role, category, subject, description, priority,
             attachment_url, resource_type, resource_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'soumise')
        RETURNING id, status, created_at
        """,
        (
            user["user_id"], user["role"], payload.category, payload.subject,
            payload.description, payload.priority, None, payload.resource_type, payload.resource_id,
        ),
    )
    result = cur.fetchone()
    cur.execute("SELECT id FROM users WHERE role IN ('gestionnaire','admin','municipal') AND active=TRUE")
    for (recipient_id,) in cur.fetchall():
        create_notification(conn, recipient_id, "support_received", "Nouvelle demande", f"Une demande « {payload.subject} » a été reçue.", "/gestionnaire#support", "notification.support_received", {"request_id": result[0], "subject": payload.subject}, resource_type="support", resource_id=result[0])
    conn.commit()
    cur.close()
    conn.close()
    return {"id": result[0], "status": result[1], "created_at": result[2]}


@router.post("/gestionnaire/collectes/generer")
def generate_collections(
    payload: OccurrenceGenerationRequest,
    user: dict = Depends(require_manager),
):
    from datetime import date
    try:
        start = date.fromisoformat(payload.start)
        until = date.fromisoformat(payload.until)
    except ValueError as exc:
        raise HTTPException(422, "Dates ISO invalides") from exc
    if until < start:
        raise HTTPException(422, "La date de fin doit être postérieure")
    conn = get_db_connection()
    created = generate_database_occurrences(conn, start, until)
    conn.close()
    return {"created": created, "start": start, "until": until}


@router.post("/gestionnaire/gps/purger")
def purge_gps_positions(user: dict = Depends(require_manager)):
    conn = get_db_connection()
    deleted = purge_old_positions(conn)
    conn.close()
    return {"deleted": deleted}


@router.get("/demandes-support/mes-demandes")
def list_my_support_requests(user: dict = Depends(current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, author_role, category, subject, description, priority, status,
               manager_response, created_at, updated_at
        FROM support_requests
        WHERE author_id = %s
        ORDER BY created_at DESC
        """,
        (user["user_id"],),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.get("/notifications")
def list_notifications(user: dict = Depends(current_user), limit: int = 20, offset: int = 0, unread: Optional[bool] = None):
    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(422, "Pagination invalide")
    conn = get_db_connection()
    from psycopg2.extras import RealDictCursor
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT id, notification_type, title, content, link,
               translation_key, translation_params, is_read, read_at, resource_type,
               resource_id, created_at
        FROM notifications
        WHERE recipient_id = %s AND (%s IS NULL OR is_read = NOT %s)
        ORDER BY created_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        (user["user_id"], unread, unread, limit, offset),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.get("/notifications/unread-count")
def unread_notification_count(user: dict = Depends(current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM notifications WHERE recipient_id = %s AND is_read = FALSE",
        (user["user_id"],),
    )
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"count": count}


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, user: dict = Depends(current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE notifications SET is_read = TRUE, read_at = COALESCE(read_at, NOW())
        WHERE id = %s AND recipient_id = %s
        RETURNING id, is_read
        """,
        (notification_id, user["user_id"]),
    )
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Notification non trouvée")
    return {"id": result[0], "is_read": result[1]}


@router.patch("/notifications/read-all")
def mark_all_notifications_read(user: dict = Depends(current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE notifications SET is_read = TRUE, read_at = NOW() WHERE recipient_id = %s AND is_read = FALSE",
        (user["user_id"],),
    )
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return {"updated": updated}


@router.get("/gestionnaire/demandes-support")
def list_support_requests(user: dict = Depends(require_manager)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, author_id, author_role, category, subject, description, priority,
               status, assigned_to, manager_response, created_at, updated_at
        FROM support_requests
        ORDER BY created_at DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.patch("/gestionnaire/demandes-support/{request_id}/reponse")
def respond_to_support_request(
    request_id: int,
    payload: SupportResponseUpdate,
    user: dict = Depends(require_manager),
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE support_requests
        SET manager_response = %s, status = 'reponse_envoyee', updated_at = NOW()
        WHERE id = %s
        RETURNING id, author_id, subject, author_role
        """,
        (payload.response, request_id),
    )
    result = cur.fetchone()
    if not result:
        cur.close()
        conn.close()
        raise HTTPException(404, "Demande non trouvée")
    create_notification(
        conn, result[1], "support_response", "Réponse à votre réclamation",
        f"Une réponse a été apportée à « {result[2]} ».",
        f"/{role_home(result[3])}#support-{result[0]}", "notification.support_response",
        {"request_id": result[0], "subject": result[2]}, resource_type="support", resource_id=result[0],
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"id": result[0], "status": "reponse_envoyee"}


@router.patch("/gestionnaire/demandes-support/{request_id}/status")
def update_support_status(request_id: int, payload: SupportStatusUpdate, user: dict = Depends(require_manager)):
    if payload.status not in SUPPORT_STATUSES:
        raise HTTPException(422, "Statut de support invalide")
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT status FROM support_requests WHERE id=%s FOR UPDATE", (request_id,))
    previous = cur.fetchone()
    if not previous:
        cur.close(); conn.close(); raise HTTPException(404, "Demande non trouvée")
    cur.execute("UPDATE support_requests SET status=%s, updated_at=NOW(), closed_at=CASE WHEN %s='cloturee' THEN NOW() ELSE NULL END WHERE id=%s RETURNING author_id,author_role,subject", (payload.status, payload.status, request_id))
    author_id, author_role, subject = cur.fetchone()
    cur.execute("INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,resource_id,old_value,new_value) VALUES (%s,%s,'support_status_changed','support',%s,%s,%s)", (user["user_id"], user["role"], request_id, Json({"status": previous[0]}), Json({"status": payload.status})))
    create_notification(conn, author_id, "support_status_changed", "Demande mise à jour", f"Le statut de « {subject} » a changé.", f"/{role_home(author_role)}#support-{request_id}", "notification.support_status_changed", {"request_id": request_id, "status": payload.status}, resource_type="support", resource_id=request_id)
    conn.commit(); cur.close(); conn.close()
    return {"id": request_id, "status": payload.status}


@router.get("/gestionnaire/plans")
def list_plans(user: dict = Depends(require_manager)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, frequency, price, service_area, active FROM subscription_plans ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.post("/gestionnaire/plans")
def create_plan(payload: PlanCreate, user: dict = Depends(require_manager)):
    if payload.frequency not in {"hebdomadaire", "bimensuelle", "mensuelle"}:
        raise HTTPException(422, "Fréquence invalide")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO subscription_plans (name, frequency, price, service_area)
        VALUES (%s, %s, %s, %s) RETURNING id, name, frequency, price, service_area, active
        """,
        (payload.name, payload.frequency, payload.price, payload.service_area),
    )
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return result


@router.get("/gestionnaire/professionnels")
def list_professionals(user: dict = Depends(require_manager)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, email, role, arrondissement, active, service_area,
               daily_capacity, available_weekdays
        FROM users WHERE role IN ('agent', 'ramasseur') ORDER BY role, id
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.patch("/gestionnaire/professionnels/{professional_id}/status")
def update_professional_status(
    professional_id: int,
    payload: ProfessionalStatusUpdate,
    user: dict = Depends(require_manager),
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users SET active = %s
        WHERE id = %s AND role IN ('agent', 'ramasseur')
        RETURNING id, role, active
        """,
        (payload.active, professional_id),
    )
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Professionnel non trouvé")
    return {"id": result[0], "role": result[1], "active": result[2]}


@router.get("/gestionnaire/collectes")
def list_all_collections(user: dict = Depends(require_manager)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.id, o.subscription_id, o.collector_id, o.scheduled_for, o.status,
               o.missed_reason, s.user_id, s.service_area
        FROM collection_occurrences o
        JOIN domestic_subscriptions s ON s.id = o.subscription_id
        ORDER BY o.scheduled_for
        LIMIT 500
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.get("/gestionnaire/signalements-operationnels")
def list_operational_reports(user: dict = Depends(require_manager)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.id, r.status, r.severity, r.address_text, r.agent_id,
               p.id, p.status, d.id, d.status
        FROM reports r
        LEFT JOIN LATERAL (
            SELECT id, status FROM report_proofs WHERE report_id=r.id
            ORDER BY created_at DESC, id DESC LIMIT 1
        ) p ON TRUE
        LEFT JOIN LATERAL (
            SELECT id, status FROM report_disputes WHERE report_id=r.id
            ORDER BY created_at DESC, id DESC LIMIT 1
        ) d ON TRUE
        WHERE r.status IN ('valide','assigne','en_cours','verification_requise','cloture','reouvert')
        ORDER BY r.updated_at DESC LIMIT 500
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.get("/gestionnaire/audit-logs")
def list_audit_logs(user: dict = Depends(require_manager)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, actor_id, actor_role, action, resource_type, resource_id,
               old_value, new_value, reason, created_at
        FROM audit_logs ORDER BY created_at DESC LIMIT 500
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.get("/ramasseur/collectes")
def list_collector_collections(user: dict = Depends(require_collector)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.id, o.subscription_id, o.scheduled_for, o.status, o.missed_reason,
               ST_Y(s.address_geometry) AS lat, ST_X(s.address_geometry) AS lon,
               s.service_area, s.preferred_slot_id
        FROM collection_occurrences o
        JOIN domestic_subscriptions s ON s.id = o.subscription_id
        WHERE o.collector_id = %s
        ORDER BY o.scheduled_for
        """,
        (user["user_id"],),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@router.get("/citoyen/collectes")
def list_citizen_collections(user: dict = Depends(require_citizen)):
    conn=get_db_connection();cur=conn.cursor()
    cur.execute("""SELECT o.id,o.scheduled_for,o.status,o.proof_media_asset_id,o.confirmation_due_at,s.address_text
        FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id
        WHERE s.user_id=%s ORDER BY o.scheduled_for DESC LIMIT 200""",(user["user_id"],));rows=cur.fetchall();cur.close();conn.close();return rows


@router.get("/agent/signalements")
def list_agent_reports(user: dict = Depends(current_user)):
    if user.get("role")!="agent": raise HTTPException(403,"Réservé aux agents")
    conn=get_db_connection();cur=conn.cursor();cur.execute("SELECT id,status,severity,address_text,proof_media_asset_id,updated_at FROM reports WHERE agent_id=%s ORDER BY updated_at DESC LIMIT 200",(user["user_id"],));rows=cur.fetchall();cur.close();conn.close();return rows


@router.post("/gestionnaire/collectes/{occurrence_id}/affecter")
def assign_collection(
    occurrence_id: int,
    payload: CollectorAssignment,
    user: dict = Depends(require_manager),
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.scheduled_for::date, s.service_area, o.status
        FROM collection_occurrences o
        JOIN domestic_subscriptions s ON s.id = o.subscription_id
        WHERE o.id = %s
        """,
        (occurrence_id,),
    )
    occurrence = cur.fetchone()
    if not occurrence:
        cur.close()
        conn.close()
        raise HTTPException(404, "Occurrence non trouvée")
    if occurrence[2] not in {"programmee", "reprogrammee"}:
        cur.close()
        conn.close()
        raise HTTPException(409, "Occurrence déjà traitée")
    cur.execute(
        """
        SELECT id, service_area, daily_capacity, available_weekdays
        FROM users
        WHERE id = %s AND role = 'ramasseur' AND active = TRUE
        """,
        (payload.collector_id,),
    )
    collector = cur.fetchone()
    if not collector:
        cur.close()
        conn.close()
        raise HTTPException(404, "Ramasseur actif non trouvé")
    scheduled_date, service_area = occurrence[0], occurrence[1]
    if collector[1] and service_area and collector[1] != service_area:
        cur.close()
        conn.close()
        raise HTTPException(409, "Ramasseur hors zone")
    if scheduled_date.weekday() not in (collector[3] or []):
        cur.close()
        conn.close()
        raise HTTPException(409, "Ramasseur indisponible ce jour")
    cur.execute(
        """
        SELECT COUNT(*) FROM collection_occurrences
        WHERE collector_id = %s AND scheduled_for::date = %s
          AND status NOT IN ('manquee', 'reprogrammee') AND id <> %s
        """,
        (collector[0], scheduled_date, occurrence_id),
    )
    if cur.fetchone()[0] >= collector[2]:
        cur.close()
        conn.close()
        raise HTTPException(409, "Capacité journalière atteinte")
    cur.execute(
        """
        UPDATE collection_occurrences
        SET collector_id = %s, status = 'proposee', response_due_at=NOW() + (%s || ' hours')::interval, updated_at = NOW()
        WHERE id = %s
        RETURNING id, collector_id, status
        """,
        (collector[0], int(__import__('os').getenv('COLLECTOR_RESPONSE_HOURS','24')), occurrence_id),
    )
    result = cur.fetchone()
    cur.execute("INSERT INTO assignment_history(resource_type,resource_id,assignee_id,actor_id,action,reason) VALUES ('collection',%s,%s,%s,'assigned',%s)",(occurrence_id,collector[0],user["user_id"],payload.reason))
    cur.execute("INSERT INTO collection_transition_history(occurrence_id,actor_id,actor_role,from_status,to_status,reason) VALUES (%s,%s,%s,%s,'proposee',%s)",(occurrence_id,user["user_id"],user["role"],occurrence[2],payload.reason))
    notify_collection(
        conn, collector[0], occurrence_id, "collection_assigned",
        "Nouvelle collecte affectée",
        f"La collecte #{occurrence_id} vous a été affectée.",
        scheduled_for=scheduled_date.isoformat(), service_area=service_area or "",
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"id": result[0], "collector_id": result[1], "status": result[2]}


@router.patch("/ramasseur/collectes/{occurrence_id}/proposition")
def respond_collection_proposal(occurrence_id:int,payload:CollectorProposalResponse,user=Depends(require_collector)):
    if not payload.accept and not (payload.reason or "").strip(): raise HTTPException(422,"Motif de refus obligatoire")
    conn=get_db_connection();cur=conn.cursor();cur.execute("SELECT o.status,s.user_id FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE o.id=%s AND o.collector_id=%s FOR UPDATE",(occurrence_id,user["user_id"]));row=cur.fetchone()
    if not row: cur.close();conn.close();raise HTTPException(404,"Collecte non trouvée")
    if row[0] not in {"proposee","affectee"}: cur.close();conn.close();raise HTTPException(409,"Proposition déjà traitée")
    target="acceptee" if payload.accept else "refusee"
    cur.execute("UPDATE collection_occurrences SET status=%s,collector_id=CASE WHEN %s THEN collector_id ELSE NULL END,refusal_reason=%s,updated_at=NOW() WHERE id=%s",(target,payload.accept,payload.reason,occurrence_id))
    cur.execute("INSERT INTO assignment_history(resource_type,resource_id,assignee_id,actor_id,action,reason) VALUES ('collection',%s,%s,%s,%s,%s)",(occurrence_id,user["user_id"],user["user_id"],"accepted" if payload.accept else "refused",payload.reason))
    cur.execute("INSERT INTO collection_transition_history(occurrence_id,actor_id,actor_role,from_status,to_status,reason) VALUES (%s,%s,%s,%s,%s,%s)",(occurrence_id,user["user_id"],user["role"],row[0],target,payload.reason))
    create_notification(conn,row[1],"collection_proposal_response","Collecte mise à jour",f"La proposition de collecte #{occurrence_id} a été {'acceptée' if payload.accept else 'refusée'}.",f"/citoyen#collecte-{occurrence_id}","notification.collection_proposal_response",{"collection_id":occurrence_id,"status":target},resource_type="collection",resource_id=occurrence_id)
    conn.commit();cur.close();conn.close();return {"id":occurrence_id,"status":target}


@router.patch("/ramasseur/collectes/{occurrence_id}/status")
def update_collector_collection(
    occurrence_id: int,
    payload: CollectionStatusUpdate,
    user: dict = Depends(require_collector),
):
    if payload.status not in {"en_route", "arrivee", "manquee"}:
        raise HTTPException(400, "Transition non autorisée pour un ramasseur")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT status FROM collection_occurrences WHERE id = %s AND collector_id = %s",
        (occurrence_id, user["user_id"]),
    )
    current = cur.fetchone()
    if not current:
        cur.close()
        conn.close()
        raise HTTPException(404, "Collecte non trouvée ou non affectée")
    if not can_transition(COLLECTION_TRANSITIONS, current[0], payload.status):
        cur.close()
        conn.close()
        raise HTTPException(409, "Transition de collecte invalide")
    if payload.status == "manquee" and not payload.missed_reason:
        cur.close()
        conn.close()
        raise HTTPException(422, "Le motif est obligatoire pour une collecte manquée")
    cur.execute(
        """
        UPDATE collection_occurrences
        SET status = %s, missed_reason = %s,
            started_at = CASE WHEN %s = 'en_route' THEN NOW() ELSE started_at END,
            arrived_at = CASE WHEN %s = 'arrivee' THEN NOW() ELSE arrived_at END,
            incident_comment = %s,
            updated_at = NOW()
        WHERE id = %s AND collector_id = %s
        RETURNING id, status
        """,
        (
            payload.status, payload.missed_reason, payload.status, payload.status,
            payload.comment, occurrence_id, user["user_id"],
        ),
    )
    result = cur.fetchone()
    cur.execute("INSERT INTO collection_transition_history(occurrence_id,actor_id,actor_role,from_status,to_status,reason) VALUES (%s,%s,%s,%s,%s,%s)",(occurrence_id,user["user_id"],user["role"],current[0],payload.status,payload.missed_reason or payload.comment))
    if payload.status == "manquee":
        notify_collection(
            conn, user["user_id"], occurrence_id, "collection_missed",
            "Collecte manquée enregistrée",
            f"La collecte #{occurrence_id} a été enregistrée comme manquée.",
            reason=payload.missed_reason,
        )
    conn.commit()
    cur.close()
    conn.close()
    return {"id": result[0], "status": result[1]}


@router.post("/ramasseur/collectes/{occurrence_id}/preuve")
async def submit_collection_proof(occurrence_id:int,file:UploadFile=File(...),comment:Optional[str]=Form(None),user=Depends(require_collector)):
    content=await read_validated_image(file);conn=get_db_connection();cur=conn.cursor();cur.execute("SELECT o.status,s.user_id FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE o.id=%s AND o.collector_id=%s FOR UPDATE",(occurrence_id,user["user_id"]));row=cur.fetchone()
    if not row: cur.close();conn.close();raise HTTPException(404,"Collecte non trouvée")
    if row[0]!="arrivee": cur.close();conn.close();raise HTTPException(409,"La collecte doit être à l'état arrivée")
    asset_id,_=store_media_with_compensation(conn,user["user_id"],"collection_proof",content,file.content_type,"collection",occurrence_id,"active",get_media_storage())
    hours=int(__import__('os').getenv('COLLECTION_CONFIRMATION_HOURS','48'))
    cur.execute("UPDATE collection_occurrences SET status='en_attente_confirmation',proof_media_asset_id=%s,proof_submitted_at=NOW(),completed_at=NOW(),confirmation_due_at=NOW()+(%s||' hours')::interval,incident_comment=%s,updated_at=NOW() WHERE id=%s",(asset_id,hours,comment,occurrence_id))
    cur.execute("INSERT INTO collection_transition_history(occurrence_id,actor_id,actor_role,from_status,to_status,reason) VALUES (%s,%s,%s,%s,'en_attente_confirmation',%s)",(occurrence_id,user["user_id"],user["role"],row[0],comment))
    create_notification(conn,row[1],"collection_proof_submitted","Collecte à confirmer",f"La collecte #{occurrence_id} attend votre confirmation.",f"/citoyen#collecte-{occurrence_id}","notification.collection_proof_submitted",{"collection_id":occurrence_id},resource_type="collection",resource_id=occurrence_id)
    conn.commit();cur.close();conn.close();return {"id":occurrence_id,"status":"en_attente_confirmation","media_asset_id":asset_id}


@router.patch("/citoyen/collectes/{occurrence_id}/decision")
def decide_collection(occurrence_id:int,payload:CitizenCollectionDecision,user=Depends(require_citizen)):
    if not payload.confirm and not (payload.reason or "").strip(): raise HTTPException(422,"Motif de contestation obligatoire")
    conn=get_db_connection();cur=conn.cursor();cur.execute("SELECT o.status,o.collector_id FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE o.id=%s AND s.user_id=%s FOR UPDATE",(occurrence_id,user["user_id"]));row=cur.fetchone()
    if not row: cur.close();conn.close();raise HTTPException(404,"Collecte non trouvée")
    if row[0]!="en_attente_confirmation": cur.close();conn.close();raise HTTPException(409,"Collecte non confirmable")
    target="confirmee" if payload.confirm else "contestee";cur.execute("UPDATE collection_occurrences SET status=%s,confirmed_at=CASE WHEN %s THEN NOW() ELSE NULL END,updated_at=NOW() WHERE id=%s",(target,payload.confirm,occurrence_id));cur.execute("INSERT INTO collection_transition_history(occurrence_id,actor_id,actor_role,from_status,to_status,reason) VALUES (%s,%s,%s,%s,%s,%s)",(occurrence_id,user["user_id"],user["role"],row[0],target,payload.reason))
    if not payload.confirm: cur.execute("INSERT INTO support_requests(author_id,author_role,category,subject,description,priority,resource_type,resource_id,status) VALUES (%s,'citoyen','preuve_contestee',%s,%s,'haute','collection',%s,'soumise')",(user["user_id"],f"Collecte #{occurrence_id} contestée",payload.reason,occurrence_id))
    if row[1]: notify_collection(conn,row[1],occurrence_id,"collection_confirmed" if payload.confirm else "collection_disputed","Collecte mise à jour",f"La collecte #{occurrence_id} est {target}.",status=target)
    conn.commit();cur.close();conn.close();return {"id":occurrence_id,"status":target}


@router.patch("/gestionnaire/collectes/{occurrence_id}/reprogrammer")
def reschedule_collection(
    occurrence_id: int,
    payload: CollectionScheduleUpdate,
    user: dict = Depends(require_manager),
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE collection_occurrences
        SET scheduled_for = %s, status = 'reprogrammee', updated_at = NOW()
        WHERE id = %s AND status NOT IN ('effectuee', 'confirmee', 'annulee')
        RETURNING id, collector_id, scheduled_for
        """,
        (payload.scheduled_for, occurrence_id),
    )
    result = cur.fetchone()
    if not result:
        cur.close(); conn.close()
        raise HTTPException(404, "Collecte modifiable non trouvée")
    if result[1]:
        notify_collection(
            conn, result[1], result[0], "collection_rescheduled",
            "Collecte reprogrammée", f"La collecte #{result[0]} a été reprogrammée.",
            scheduled_for=result[2].isoformat(),
        )
    conn.commit(); cur.close(); conn.close()
    return {"id": result[0], "status": "reprogrammee", "scheduled_for": result[2]}


@router.patch("/gestionnaire/collectes/{occurrence_id}/annuler")
def cancel_collection(occurrence_id: int, user: dict = Depends(require_manager)):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute(
        """UPDATE collection_occurrences SET status = 'annulee', updated_at = NOW()
           WHERE id = %s AND status NOT IN ('effectuee', 'confirmee', 'annulee')
           RETURNING id, collector_id""",
        (occurrence_id,),
    )
    result = cur.fetchone()
    if not result:
        cur.close(); conn.close()
        raise HTTPException(404, "Collecte annulable non trouvée")
    if result[1]:
        notify_collection(
            conn, result[1], result[0], "collection_cancelled",
            "Collecte annulée", f"La collecte #{result[0]} a été annulée.",
        )
    conn.commit(); cur.close(); conn.close()
    return {"id": result[0], "status": "annulee"}


@router.post("/gestionnaire/collectes/{occurrence_id}/rappel")
def remind_collection(occurrence_id: int, user: dict = Depends(require_manager)):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute(
        """SELECT id, collector_id, scheduled_for FROM collection_occurrences
           WHERE id = %s AND collector_id IS NOT NULL
             AND status IN ('affectee', 'en_route', 'arrivee', 'reprogrammee')""",
        (occurrence_id,),
    )
    result = cur.fetchone()
    if not result:
        cur.close(); conn.close()
        raise HTTPException(404, "Collecte affectée non trouvée")
    notify_collection(
        conn, result[1], result[0], "collection_reminder",
        "Rappel de collecte", f"Rappel pour la collecte #{result[0]}.",
        scheduled_for=result[2].isoformat(),
    )
    conn.commit(); cur.close(); conn.close()
    return {"id": result[0], "reminder_sent": True}
