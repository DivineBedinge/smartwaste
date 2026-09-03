from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from core.policy import COLLECTION_TRANSITIONS, can_transition, is_manager_role
from app.services.collections import generate_database_occurrences
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


class CollectionStatusUpdate(BaseModel):
    status: str
    missed_reason: Optional[str] = Field(default=None, max_length=64)


class OccurrenceGenerationRequest(BaseModel):
    start: str
    until: str


@router.post("/abonnements-domestiques")
def create_domestic_subscription(
    payload: SubscriptionCreate,
    user: dict = Depends(require_citizen),
):
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO support_requests
            (author_id, author_role, category, subject, description, priority, attachment_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, status, created_at
        """,
        (
            user["user_id"], user["role"], payload.category, payload.subject,
            payload.description, payload.priority, payload.attachment_url,
        ),
    )
    result = cur.fetchone()
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


@router.patch("/ramasseur/collectes/{occurrence_id}/status")
def update_collector_collection(
    occurrence_id: int,
    payload: CollectionStatusUpdate,
    user: dict = Depends(require_collector),
):
    if payload.status not in {"en_route", "arrivee", "effectuee", "manquee"}:
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
            completed_at = CASE WHEN %s = 'effectuee' THEN NOW() ELSE completed_at END,
            updated_at = NOW()
        WHERE id = %s AND collector_id = %s
        RETURNING id, status
        """,
        (
            payload.status, payload.missed_reason, payload.status, payload.status,
            payload.status, occurrence_id, user["user_id"],
        ),
    )
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"id": result[0], "status": result[1]}