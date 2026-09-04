import re
import asyncio
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse,Response
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
import psycopg2
import psycopg2.extras
import numpy as np
import csv, io
import base64
import json
from PIL import Image
import os
from uuid import UUID
from dotenv import load_dotenv
from pydantic import BaseModel
from database import get_db_connection
from auth import router as auth_router
from core.security import decode_token
from core.classification import decide_severity
from core.policy import REPORT_TRANSITIONS, can_transition, is_agent_role, is_manager_role
from normalizer import normaliser_et_corriger, detecter_langue, extraire_mots_cles
from chatbot_utils import (
    generer_embedding, recherche_rag, construire_contexte,
    appeler_llm, verifier_reponse,
    recherche_vectorielle, recherche_bm25, reciprocal_rank_fusion,
    rerank, generer_reponse_avec_contexte,traduire_en_anglais
)
from typing import Optional, List
from redis_utils import (
    obtenir_reponse_cachee,
    enregistrer_reponse_cachee,
    obtenir_memoire_session,
    ajouter_message_session,
    obtenir_types_precedents
)
from chatbot_utils import formuler_reponse_humaine
from session_manager import session_manager
from app.router import chatbot_cache_key, detect_simple_intent, is_faq_question, simple_chat_response
from route_optimizer import get_graph, calculer_matrice_distances, resoudre_vrp
from app.routers.workflows import router as workflows_router
from app.routers.communications import router as communications_router
from app.services.uploads import read_validated_image
from app.services.routing import get_route
from app.services.notifications import (
    acknowledge_notification_event,
    create_notification,
    pending_notification_events,
    record_notification_failure,
)
from app.services.gps_tracking import PositionRateLimiter
from app.services.ai_runtime import get_onnx_session, heavy_ai_disabled, runtime_status
from fastapi import APIRouter, Depends, HTTPException, status



# ========== CONFIGURATION ==========
MAPPING_DECHETS = {
    'pile': 'battery', 'batterie': 'battery', 'battery': 'battery',
    'bouteille': 'plastic', 'plastique': 'plastic', 'plastic': 'plastic', 'sachet': 'plastic',
    'canette': 'metal', 'metal': 'metal',
    'can': 'metal', 'metal': 'metal',
    'verre': 'glass', 'glass': 'glass',
    'papier': 'paper', 'paper': 'paper',
    'carton': 'cardboard', 'cardboard': 'cardboard',
    'organique': 'biological', 'biological': 'biological', 'nourriture': 'biological',
    'reste': 'biological', 'epluchure': 'biological', 'organic': 'biological',
    'vetement': 'clothes', 'clothes': 'clothes', 'chaussure': 'shoes', 'shoes': 'shoes',
    'dechet': 'trash', 'trash': 'trash', 'poubelle': 'trash', 'jeter': 'trash',
    'chaise': 'encombrant', 'chair': 'encombrant', 'meuble': 'encombrant',
    'table': 'encombrant', 'matelas': 'encombrant', 'armoire': 'encombrant',
    'fauteuil': 'encombrant', 'electromenager': 'encombrant', 'frigo': 'encombrant',
    'television': 'encombrant', 'furniture': 'encombrant',
    'ananas': 'biological', 'pineapple': 'biological', 'pomme': 'biological',
    'apple': 'biological', 'fruit': 'biological', 'legume': 'biological',
    'vegetable': 'biological', 'rotten': 'biological', 'pourri': 'biological',
    'pourriture': 'biological',
    'aluminium': 'metal', 'aluminui': 'metal', 'alu': 'metal',
    'manguier': 'biological',
    'feuille': 'biological',
    'feuilles': 'biological',
    'branche': 'biological',
    'branches': 'biological',
    'cans': 'metal',           # ← ajout
    'banane': 'biological',   # ← ajout
    'bananes': 'biological',  # ← ajout
    'cheveu': 'biological',   # ← ajout
    'cheveux': 'biological',  # ← ajout
    'peau': 'biological',     # ← ajout (épluchures)
    'épluchure': 'biological',# déjà présent
}


salutations = [
    'bonjour', 'bonsoir', 'salut', 'hello', 'good morning', 'goodmorning',
    'good evening', 'goodevening', 'morning', 'evening', 'on dit quoi',
    'bjr', 'bsr', 'hi', 'hey', 'coucou', 'yo', 'wesh', 'salam'
]
FAQ_RELEVANCE_THRESHOLD = 0.30

class TourneeCreate(BaseModel):
    agent_id: int
    signalement_ids: List[int]
    date_planifiee: str = None

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))
GPS_UPDATE_INTERVAL_SECONDS = float(os.getenv("GPS_UPDATE_INTERVAL_SECONDS", "10"))
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",") if origin.strip()]
gps_rate_limiter = PositionRateLimiter(GPS_UPDATE_INTERVAL_SECONDS)

# ========== MODÈLE 4 CLASSES (SÉVÉRITÉ) – pour signalements ==========
MODEL_SEVERITY_PATH = os.getenv("MODEL_SEVERITY_PATH", "./smartwaste_mobilenetv2_clean.onnx")
MODEL_VERSION = os.getenv("MODEL_VERSION", "unknown")
CLASS_NAMES_SEVERITY = ["faible", "moderee", "critique", "hors_sujet"]

# ========== MODÈLE 12 CLASSES (TYPE) – pour le chatbot ==========
MODEL_TYPE_PATH = os.getenv("MODEL_TYPE_PATH", "./modele_12classes.onnx")
CLASS_NAMES_TYPE = [
    'battery', 'biological', 'brown-glass', 'cardboard', 'clothes',
    'green-glass', 'metal', 'paper', 'plastic', 'shoes', 'trash', 'white-glass'
]

# ========== MODÈLE 2 CLASSES (RECYCLABLE / ORGANIQUE) – pour le chatbot ==========
MODEL_BINARY_PATH = os.getenv("MODEL_BINARY_PATH", "./modele_2classes.onnx")
CLASS_NAMES_BINARY = ["organique", "recyclable"]

app = FastAPI(title="SmartWaste CM+ API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dossier statique
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_router)
app.include_router(workflows_router)
app.include_router(communications_router)

# Sécurité
security = HTTPBearer()

def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload or not is_manager_role(payload.get("role", "")):
        raise HTTPException(403, "Accès refusé")
    return payload

def require_agent(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload or not is_agent_role(payload.get("role", ""), include_managers=True):
        raise HTTPException(403, "Accès refusé")
    return payload

def is_manager(payload: dict) -> bool:
    return is_manager_role(payload.get("role", ""))

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide ou expiré")
    return payload

# ========== GESTION DES CONNEXIONS WEBSOCKET ==========
class WSManager:
    def __init__(self):
        self.connections: dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, user: dict):
        await websocket.accept()
        self.connections[websocket] = {"user_id": user["user_id"], "role": user["role"]}

    def disconnect(self, websocket: WebSocket):
        self.connections.pop(websocket, None)

    async def _send_where(self, message: dict, predicate):
        for conn, identity in list(self.connections.items()):
            if not predicate(identity):
                continue
            try:
                await conn.send_text(json.dumps(message))
            except Exception:
                self.disconnect(conn)

    async def send_to_user(self, user_id: int, message: dict):
        await self._send_where(message, lambda identity: identity["user_id"] == user_id)

    async def send_to_managers(self, message: dict):
        await self._send_where(message, lambda identity: is_manager_role(identity["role"]))

ws_manager = WSManager()
notification_dispatch_task = None


async def dispatch_notification_outbox_once(connection=None):
    conn = connection or get_db_connection()
    owns_connection = connection is None
    try:
        for event in pending_notification_events(conn):
            payload = {key: value for key, value in event.items() if key != "recipient_id"}
            if payload.get("created_at") is not None:
                payload["created_at"] = payload["created_at"].isoformat()
            try:
                await ws_manager.send_to_user(event["recipient_id"], {"event": "notification", **payload})
                acknowledge_notification_event(conn, event["notification_id"])
            except Exception as error:
                record_notification_failure(conn, event["notification_id"], str(error))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_connection:
            conn.close()


async def notification_dispatch_loop():
    while True:
        try:
            await dispatch_notification_outbox_once()
        except Exception:
            pass
        await asyncio.sleep(2)


@app.on_event("startup")
async def start_notification_dispatcher():
    global notification_dispatch_task
    if notification_dispatch_task is None or notification_dispatch_task.done():
        notification_dispatch_task = asyncio.create_task(notification_dispatch_loop())


@app.on_event("shutdown")
async def stop_notification_dispatcher():
    global notification_dispatch_task
    if notification_dispatch_task:
        notification_dispatch_task.cancel()
        try:
            await notification_dispatch_task
        except asyncio.CancelledError:
            pass
        notification_dispatch_task = None

class AgentCreate(BaseModel):
    email: str
    password: str
    arrondissement: str = None
    type_agent: str = "officiel"

class AgentUpdate(BaseModel):
    arrondissement: str = None
    type_agent: str = None

@app.post("/api/v1/agents")
def creer_agent(payload: AgentCreate, user: dict = Depends(require_admin)):
    from core.security import hash_password
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (payload.email,))
    if cur.fetchone():
        raise HTTPException(400, "Email déjà utilisé")
    cur.execute("""INSERT INTO users (email, password_hash, role, arrondissement)
                   VALUES (%s,%s,'agent',%s) RETURNING id""",
                (payload.email, hash_password(payload.password), payload.arrondissement))
    agent_id = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return {"id": agent_id, "email": payload.email, "role": "agent", "arrondissement": payload.arrondissement}


class CollectorCreate(BaseModel):
    email: str
    password: str
    arrondissement: str = None


@app.post("/api/v1/ramasseurs")
def creer_ramasseur(payload: CollectorCreate, user: dict = Depends(require_admin)):
    from core.security import hash_password
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (payload.email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(400, "Email déjà utilisé")
    cur.execute(
        """
        INSERT INTO users (email, password_hash, role, arrondissement)
        VALUES (%s, %s, 'ramasseur', %s) RETURNING id
        """,
        (payload.email, hash_password(payload.password), payload.arrondissement),
    )
    collector_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {
        "id": collector_id,
        "email": payload.email,
        "role": "ramasseur",
        "arrondissement": payload.arrondissement,
    }

@app.put("/api/v1/agents/{agent_id}")
def modifier_agent(agent_id: int, payload: AgentUpdate, user: dict = Depends(require_admin)):
    conn = get_db_connection(); cur = conn.cursor()
    if payload.arrondissement:
        cur.execute("UPDATE users SET arrondissement=%s WHERE id=%s AND role='agent' RETURNING id",
                    (payload.arrondissement, agent_id))
    else:
        cur.execute("SELECT id FROM users WHERE id=%s AND role='agent'", (agent_id,))
    result = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    if not result:
        raise HTTPException(404, "Agent non trouvé")
    return {"message": "Agent mis à jour"}

class CommentaireUpdate(BaseModel):
    commentaire: str


class HumanReviewUpdate(BaseModel):
    final_severity: str
    reason: str
    out_of_scope: bool = False


class SignalementStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None

@app.put("/api/v1/signalements/{report_id}/commentaire")
def ajouter_commentaire(report_id: int, payload: CommentaireUpdate, user: dict = Depends(require_admin)):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("UPDATE reports SET commentaire_gestion=%s WHERE id=%s RETURNING id",
                (payload.commentaire, report_id))
    result = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    if not result:
        raise HTTPException(404, "Signalement non trouvé")
    return {"message": "Commentaire enregistré"}


@app.put("/api/v1/signalements/{report_id}/review")
def review_signalement(
    report_id: int,
    payload: HumanReviewUpdate,
    user: dict = Depends(require_admin),
):
    if payload.final_severity not in ["faible", "moderee", "critique"]:
        raise HTTPException(400, "Sévérité finale invalide")
    if not payload.reason.strip():
        raise HTTPException(422, "Le motif de décision est obligatoire")

    final_status = "hors_sujet" if payload.out_of_scope else "valide"
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT status, severity, confidence FROM reports WHERE id = %s",
        (report_id,),
    )
    report = cur.fetchone()
    if not report:
        cur.close()
        conn.close()
        raise HTTPException(404, "Signalement non trouvé")
    if not can_transition(REPORT_TRANSITIONS, report["status"], final_status):
        cur.close()
        conn.close()
        raise HTTPException(409, "Transition de revue invalide")

    cur.execute(
        """
        UPDATE reports
        SET status = %s, final_severity = %s, reviewed_by = %s,
            reviewed_at = NOW(), review_reason = %s,
            rejection_reason = CASE WHEN %s = 'hors_sujet' THEN %s ELSE NULL END,
            human_review_required = FALSE, updated_at = NOW()
        WHERE id = %s
        RETURNING id, status, final_severity
        """,
        (
            final_status, payload.final_severity, user["user_id"], payload.reason,
            final_status, payload.reason, report_id,
        ),
    )
    result = cur.fetchone()
    cur.execute(
        """
        INSERT INTO audit_logs
            (actor_id, actor_role, action, resource_type, resource_id,
             old_value, new_value, reason)
        VALUES (%s, %s, 'human_review', 'report', %s, %s, %s, %s)
        """,
        (
            user["user_id"], user["role"], report_id,
            {"status": report["status"], "severity": report["severity"]},
            {"status": final_status, "severity": payload.final_severity},
            payload.reason,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()
    return dict(result)

# ========== FONCTIONS UTILITAIRES ==========
def preprocess(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((224, 224))
    arr = np.array(img).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    arr = np.transpose(arr, (2, 0, 1))
    arr = np.expand_dims(arr, axis=0).astype(np.float32)
    return arr


def validate_coordinates(lat: float, lon: float) -> None:
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise HTTPException(422, "Coordonnées GPS invalides")

def predict_severity(image_bytes):
    session_severity = get_onnx_session(MODEL_SEVERITY_PATH)
    input_data = preprocess(image_bytes)
    input_name = session_severity.get_inputs()[0].name
    outputs = session_severity.run(None, {input_name: input_data})
    scores = outputs[0][0]
    exp_scores = np.exp(scores - np.max(scores))
    probs = exp_scores / np.sum(exp_scores)
    class_idx = int(np.argmax(probs))
    severity = CLASS_NAMES_SEVERITY[class_idx]
    confidence = float(np.max(probs))
    return severity, confidence

def predict_type(image_bytes):
    session_type = get_onnx_session(MODEL_TYPE_PATH)
    input_data = preprocess(image_bytes)
    input_data = np.transpose(input_data, (0, 2, 3, 1))
    input_name = session_type.get_inputs()[0].name
    outputs = session_type.run(None, {input_name: input_data})
    scores = outputs[0][0]
    exp_scores = np.exp(scores - np.max(scores))
    probs = exp_scores / np.sum(exp_scores)
    class_idx = int(np.argmax(probs))
    type_dechet = CLASS_NAMES_TYPE[class_idx]
    confidence = float(np.max(probs))
    return type_dechet, confidence

def predict_binary(image_bytes):
    session_binary = get_onnx_session(MODEL_BINARY_PATH)
    input_data = preprocess(image_bytes)
    input_data = np.transpose(input_data, (0, 2, 3, 1))
    input_name = session_binary.get_inputs()[0].name
    outputs = session_binary.run(None, {input_name: input_data})
    scores = outputs[0][0]
    exp_scores = np.exp(scores - np.max(scores))
    probs = exp_scores / np.sum(exp_scores)
    class_idx = int(np.argmax(probs))
    classe = CLASS_NAMES_BINARY[class_idx]
    confidence = float(np.max(probs))
    return classe, confidence

def segmenter_phrases(texte: str) -> list:
    phrases = re.split(r'(?<=[.!?])\s+', texte.strip())
    return [p.strip() for p in phrases if p.strip()]

# ========== GESTION DES DOUBLONS ==========
def find_duplicate_group(lat: float, lon: float, waste_type: str, radius_meters: int = 50):
    conn = get_db_connection()
    cur = conn.cursor()
    radius_deg = radius_meters / 111000.0
    cur.execute("""
        SELECT duplicate_group_id
        FROM reports
        WHERE waste_type = %s
          AND ST_DWithin(geometry, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
          AND is_primary = TRUE
        LIMIT 1
    """, (waste_type, lon, lat, radius_deg))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

# ========== ROUTES DE BASE ==========
@app.get("/")
def root():
    return {"message": "SmartWaste CM+ API is running"}


@app.get("/health")
def health():
    database_status = "unavailable"
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        database_status = "available" if cur.fetchone() else "unavailable"
    except Exception:
        pass
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()
    return {"api": "operational", "database": database_status, **runtime_status()}

@app.get("/dashboard")
def dashboard():
    return FileResponse("static/dashboard.html")

@app.get("/citoyen")
def citoyen():
    return FileResponse("static/citoyen.html")

@app.get("/agent")
def agent():
    return FileResponse("static/agent.html")

@app.get("/gestionnaire")
def gestionnaire():
    return FileResponse("static/gestionnaire.html")

@app.get("/agent-map")
def agent_map():
    return FileResponse("static/agent_map.html")

@app.get("/gestionnaire-map")
def gestionnaire_map():
    return FileResponse("static/gestionnaire_map.html")


@app.get("/ramasseur")
def ramasseur():
    return FileResponse("static/ramasseur.html")

# ========== WEBSOCKET ==========
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    protocols = [value.strip() for value in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    token = protocols[1] if len(protocols) == 2 and protocols[0].lower() == "bearer" else None
    user = decode_token(token) if token else None
    if not user or "user_id" not in user or "role" not in user:
        await websocket.close(code=1008)
        return
    await ws_manager.connect(websocket, user)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# ========== POINTS DE COLLECTE & SOCIÉTÉS ==========
@app.get("/api/v1/chatbot/point-proche")
def point_collecte_proche(lat: float, lon: float, type_dechet: str = None):
    """
    Retourne les points de collecte les plus proches (dans un rayon de 20 km).
    """
    # Rayon max en degrés (~20 km)
    max_distance_deg = 0.2
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    if type_dechet:
        cur.execute("""
            SELECT id, nom, type_activite, zone, arrondissement, contact,
                   ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
                   types_dechets, fiabilite, source,
                   ST_Distance(geometry, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) AS distance
            FROM points_collecte
            WHERE (%s = ANY(types_dechets) OR 'tout' = ANY(types_dechets))
              AND ST_DWithin(geometry, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
            ORDER BY distance
            LIMIT 5
        """, (lon, lat, type_dechet, lon, lat, max_distance_deg))
    else:
        cur.execute("""
            SELECT id, nom, type_activite, zone, arrondissement, contact,
                   ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
                   types_dechets, fiabilite, source,
                   ST_Distance(geometry, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) AS distance
            FROM points_collecte
            WHERE ST_DWithin(geometry, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
            ORDER BY distance
            LIMIT 5
        """, (lon, lat, lon, lat, max_distance_deg))
    
    points = cur.fetchall()
    cur.close()
    conn.close()
    
    for p in points:
        p["distance_km"] = round(p["distance"] * 111, 2)
    
    return {
        "position": {"lat": lat, "lon": lon},
        "points_proches": points
    }
@app.post("/api/v1/societes/enregistrer")
def enregistrer_societe(
    nom: str,
    type_dechets: List[str],
    lat: float,
    lon: float,
    contact: str = None,
    description: str = None,
    user: dict = Depends(require_admin)
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO points_collecte (nom, type_activite, zone, arrondissement, geometry, types_dechets, source, fiabilite, contact)
        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, 'societe', 'officiel', %s)
        RETURNING id
    """, (nom, 'Société de retraitement', 'Zone industrielle', 'Douala', lon, lat, type_dechets, contact))
    point_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": point_id, "message": "Société enregistrée avec succès"}

# ========== SIGNALEMENTS ==========
@app.post("/api/v1/signalements")
async def create_signalement(
    file: UploadFile = File(...),
    lat: float = Form(...),
    lon: float = Form(...),
    client_id: str = Form(...),
    description: Optional[str] = Form(None),
    address_text: Optional[str] = Form(None),
    current_user: dict = Depends(require_auth)  # <-- AJOUT
):
    validate_coordinates(lat, lon)
    try:
        UUID(client_id)
    except ValueError as exc:
        raise HTTPException(422, "client_id doit être un UUID valide") from exc
    image_bytes = await read_validated_image(file)
    photo_base64 = base64.b64encode(image_bytes).decode('utf-8')

    try:
        severity, confidence = predict_severity(image_bytes)
        severity_decision = decide_severity(severity, confidence)
    except Exception:
        severity, confidence = None, None
        severity_decision = decide_severity(None, None, model_error=True)
    try:
        type_dechet, _ = predict_type(image_bytes)
    except Exception:
        type_dechet = "trash"

    status = severity_decision.status

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, status, severity, confidence, waste_type FROM reports WHERE user_id = %s AND client_id = %s",
        (current_user["user_id"], client_id),
    )
    existing = cur.fetchone()
    if existing:
        cur.close()
        conn.close()
        return {"id": existing[0], "status": existing[1], "severity": existing[2], "confidence": existing[3], "type_dechet": existing[4], "duplicate": True}

    group_id = find_duplicate_group(lat, lon, type_dechet)

    if group_id is not None:
        cur.execute("""
            UPDATE reports
            SET report_count = report_count + 1,
                updated_at = NOW()
            WHERE duplicate_group_id = %s AND is_primary = TRUE
            RETURNING id
        """, (group_id,))
        primary_id = cur.fetchone()[0]
        is_primary = False
        duplicate_group_id = group_id
        report_count = 0
    else:
        is_primary = True
        duplicate_group_id = None
        report_count = 1

    # INSERT avec user_id
    cur.execute("""
        INSERT INTO reports (user_id, geometry, severity, confidence, status, photo_base64, waste_type,
                     is_primary, report_count, duplicate_group_id,
                     classification_source, classification_model_version, analyzed_at,
                                         human_review_required, initial_severity, final_severity, client_id, description, address_text)
        VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s)
        RETURNING id
        """, (current_user["user_id"], lon, lat, severity, confidence, status, photo_base64, type_dechet,
          is_primary, report_count, duplicate_group_id, severity_decision.source, MODEL_VERSION,
          severity_decision.human_review_required, severity_decision.predicted_class,
                    None if severity_decision.human_review_required else severity_decision.predicted_class,
                      client_id, description, address_text))
    report_id = cur.fetchone()[0]

    if is_primary:
        cur.execute("""
            UPDATE reports
            SET duplicate_group_id = %s
            WHERE id = %s
        """, (report_id, report_id))
        group_id = report_id

    conn.commit()
    create_notification(
        conn,
        current_user["user_id"],
        "report_received",
        "Signalement reçu",
        f"Votre signalement #{report_id} a été enregistré.",
        f"/citoyen#signalement-{report_id}",
        "notification.report_received",
        {"report_id": report_id},
    )
    conn.commit()
    cur.close()
    conn.close()

    import asyncio
    asyncio.create_task(ws_manager.send_to_managers({
        "type": "nouveau_signalement",
        "id": report_id,
        "severity": severity,
        "type_dechet": type_dechet
    }))

    return {
        "id": report_id,
        "type_dechet": type_dechet,
        "severity": severity,
        "confidence": confidence,
        "lat": lat,
        "lon": lon,
        "status": status,
        "duplicate_group_id": group_id,
        "is_primary": is_primary,
        "user_id": current_user["user_id"]
    }

@app.get("/api/v1/signalements/groupes")
def get_groupes(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT duplicate_group_id,
               MAX(id) AS primary_id,
               COUNT(*) AS nb_signalements,
               MAX(severity) AS severity,
               MAX(waste_type) AS waste_type,
               ST_AsText(ST_Centroid(ST_Collect(geometry))) AS centroid
        FROM reports
        GROUP BY duplicate_group_id
        ORDER BY nb_signalements DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ========== GUIDE DE TRI ==========
@app.get("/api/v1/sorting/guide")
def sorting_guide(q: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT keyword, waste_type, local_consigne, notes
        FROM sorting_rules
        WHERE keyword ILIKE %s
           OR EXISTS (SELECT 1 FROM unnest(aliases) a WHERE a ILIKE %s)
        LIMIT 5
    """, (f"%{q}%", f"%{q}%"))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        raise HTTPException(404, "Aucune consigne trouvée")
    return rows

# ========== CLUSTERS & HEATMAP ==========
@app.get("/api/v1/clusters")
def get_clusters(eps: float = 0.005, min_points: int = 1):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        WITH clusters AS (
            SELECT id, severity, confidence, geometry,
                   ST_ClusterDBSCAN(geometry, %s, %s) OVER () AS cluster_id
            FROM reports
            WHERE status NOT IN ('refuse', 'rejete_hors_sujet')
              AND severity != 'hors_sujet'
        )
        SELECT cluster_id, COUNT(*) AS nb_signalements,
               ST_AsText(ST_Centroid(ST_Collect(geometry))) AS centroid,
               AVG(confidence) AS confiance_moyenne
        FROM clusters
        WHERE cluster_id IS NOT NULL
        GROUP BY cluster_id
        ORDER BY nb_signalements DESC
    """, (eps, min_points))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "cluster_id": row["cluster_id"],
            "nb_signalements": row["nb_signalements"],
            "centroid": row["centroid"],
            "confiance_moyenne": float(row["confiance_moyenne"]) if row["confiance_moyenne"] else None
        }
        for row in rows
    ]

@app.get("/api/v1/heatmap")
def get_heatmap():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, severity, confidence,
               ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
               created_at
        FROM reports
        WHERE status NOT IN ('refuse', 'rejete_hors_sujet')
          AND severity != 'hors_sujet'
        ORDER BY created_at DESC
        LIMIT 1000
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            "properties": {
                "id": row["id"],
                "severity": row["severity"],
                "confidence": row["confidence"],
                "created_at": row["created_at"].isoformat()
            }
        })
    return {"type": "FeatureCollection", "features": features}

# ========== WORKFLOW SIGNALEMENTS ==========
@app.get("/api/v1/signalements/hors-sujet")
def get_hors_sujet(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, severity, confidence, status, created_at,
               ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
               photo_base64
        FROM reports
        WHERE severity = 'hors_sujet' 
           OR status IN ('rejete_hors_sujet', 'en_attente_validation')
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.put("/api/v1/signalements/{report_id}/statut")
def update_signalement_status(
    report_id: int,
    payload: SignalementStatusUpdate,
    user: dict = Depends(require_admin),
):
    if payload.status not in REPORT_TRANSITIONS:
        raise HTTPException(400, "Statut invalide")
    if payload.status in {"rejete", "hors_sujet", "reouvert"} and not (payload.reason or "").strip():
        raise HTTPException(422, "Un motif est obligatoire pour cette transition")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT status, user_id FROM reports WHERE id = %s", (report_id,))
    report = cur.fetchone()
    if not report:
        cur.close()
        conn.close()
        raise HTTPException(404, "Signalement non trouvé")
    if not can_transition(REPORT_TRANSITIONS, report["status"], payload.status):
        cur.close()
        conn.close()
        raise HTTPException(409, "Transition de signalement invalide")
    cur.execute("""
        UPDATE reports SET status = %s, updated_at = NOW()
        WHERE id = %s RETURNING id, status
    """, (payload.status, report_id))
    result = cur.fetchone()
    cur.execute("""
        INSERT INTO audit_logs
            (actor_id, actor_role, action, resource_type, resource_id,
             old_value, new_value, reason)
        VALUES (%s, %s, 'status_change', 'report', %s, %s, %s, %s)
    """, (
        user["user_id"], user["role"], report_id,
        {"status": report["status"]}, {"status": payload.status}, payload.reason,
    ))
    if report.get("user_id"):
        create_notification(
            conn, report["user_id"], "report_status_changed", "Signalement mis à jour",
            "Le statut de votre signalement a changé.",
            f"/citoyen#signalement-{report_id}", "notification.report_status_changed",
            {"report_id": report_id, "status": payload.status},
            resource_type="report", resource_id=report_id,
        )
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Signalement non trouvé")
    return {"id": result[0], "status": result[1]}

@app.put("/api/v1/signalements/{report_id}/reclasser")
def reclasser_signalement(report_id: int, nouvelle_severite: str, user: dict = Depends(require_admin)):
    valid_severites = ['faible', 'moderee', 'critique']
    if nouvelle_severite not in valid_severites:
        raise HTTPException(400, "Sévérité invalide")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reports SET severity = %s, status = 'valide', updated_at = NOW()
        WHERE id = %s RETURNING id, severity, status
    """, (nouvelle_severite, report_id))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Signalement non trouvé")
    return {"id": result[0], "severity": result[1], "status": result[2]}

@app.put("/api/v1/signalements/{report_id}/valider")
def valider_signalement(report_id: int, user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT status, agent_id, user_id FROM reports WHERE id = %s", (report_id,))
    report = cur.fetchone()
    if not report:
        raise HTTPException(404, "Signalement non trouvé")
    if report["status"] != "soumis":
        raise HTTPException(400, "Le signalement doit être 'soumis'")
    cur.execute("""
        UPDATE reports SET status = 'valide', updated_at = NOW()
        WHERE id = %s RETURNING id, status
    """, (report_id,))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"id": result["id"], "status": result["status"]}

@app.put("/api/v1/signalements/{report_id}/prendre-en-charge")
def prendre_en_charge(report_id: int, user: dict = Depends(require_agent)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT status, agent_id FROM reports WHERE id = %s", (report_id,))
    report = cur.fetchone()
    if not report:
        raise HTTPException(404, "Signalement non trouvé")
    if report["status"] != "valide":
        raise HTTPException(400, "Le signalement doit être 'valide'")
    if user["role"] == "agent" and report["agent_id"] != user["user_id"]:
        raise HTTPException(403, "Signalement non assigné à cet agent")
    cur.execute("""
        UPDATE reports SET status = 'en_cours', updated_at = NOW()
        WHERE id = %s RETURNING id, status
    """, (report_id,))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"id": result["id"], "status": result["status"]}

@app.post("/api/v1/signalements/{report_id}/preuve-traitement")
async def soumettre_preuve_traitement(
    report_id: int,
    file: UploadFile = File(...),
    lat: float = Form(...),
    lon: float = Form(...),
    user: dict = Depends(require_agent)
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT status, agent_id, user_id FROM reports WHERE id = %s", (report_id,))
    report = cur.fetchone()
    if not report:
        raise HTTPException(404, "Signalement non trouvé")
    if report["status"] != "en_cours":
        raise HTTPException(400, "Le signalement doit être 'en_cours'")
    if user["role"] == "agent" and report["agent_id"] != user["user_id"]:
        raise HTTPException(403, "Signalement non assigné à cet agent")

    validate_coordinates(lat, lon)
    image_bytes = await read_validated_image(file)
    photo_preuve_base64 = base64.b64encode(image_bytes).decode('utf-8')

    severity, confiance = predict_severity(image_bytes)

    if severity in ["faible", "hors_sujet"]:
        resultat = "valide"
        nouveau_statut = "traite"
        message = "Traitement validé par l'IA"
    else:
        resultat = "echec"
        nouveau_statut = "verification_requise"
        message = "Déchets encore présents selon l'IA. Vérification requise."

    cur.execute("""
        UPDATE reports SET status = %s, photo_preuve_base64 = %s,
               resultat_preuve = %s, confiance_preuve = %s,
               date_traitement = NOW(), updated_at = NOW()
        WHERE id = %s RETURNING id, status
    """, (nouveau_statut, photo_preuve_base64, resultat, confiance, report_id))
    result = cur.fetchone()
    create_notification(
        conn, report["user_id"], "report_proof_result", "Preuve de traitement",
        "La preuve de traitement de votre signalement a été analysée.",
        f"/citoyen#signalement-{report_id}", "notification.report_proof_result",
        {"report_id": report_id, "status": nouveau_statut, "result": resultat},
        resource_type="report", resource_id=report_id,
    )
    conn.commit()
    cur.close()
    conn.close()

    import asyncio
    asyncio.create_task(ws_manager.send_to_user(report["user_id"], {
        "type": "traitement_termine",
        "report_id": report_id,
        "status": nouveau_statut
    }))

    return {
        "id": result["id"], "status": result["status"],
        "resultat_preuve": resultat, "severite_predite": severity,
        "confiance": confiance, "message": message
    }

@app.get("/api/v1/signalements")
def get_signalements(
    statut: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if statut:
        cur.execute("""
            SELECT r.id, r.severity, r.confidence, r.status, r.waste_type,
                   ST_Y(r.geometry) AS lat, ST_X(r.geometry) AS lon,
                   r.created_at, r.updated_at,
                   r.photo_base64
            FROM reports r
            WHERE r.status = %s
            ORDER BY r.created_at DESC
        """, (statut,))
    else:
        cur.execute("""
            SELECT r.id, r.severity, r.confidence, r.status, r.waste_type,
                   ST_Y(r.geometry) AS lat, ST_X(r.geometry) AS lon,
                   r.created_at, r.updated_at,
                   r.photo_base64
            FROM reports r
            ORDER BY r.created_at DESC
        """)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
# ========== CHATBOT AVEC MÉMOIRE DE SESSION ET RAG HYBRIDE ==========

@app.get("/api/v1/chatbot/reponse")
def chatbot_reponse(question: str):
    """Ancien endpoint basé sur les mots-clés (conservé pour compatibilité)."""
    langue = detecter_langue(question)
    mots_cles = extraire_mots_cles(question)
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    prix_info = None
    connaissance = None
    points = []
    
    type_dechet = None
    for mot in mots_cles:
        if mot in MAPPING_DECHETS:
            type_dechet = MAPPING_DECHETS[mot]
            break
    
    if type_dechet:
        cur.execute("""
            SELECT prix_kg, source FROM prix_reference
            WHERE type_dechet = %s AND ville = 'Douala' LIMIT 1
        """, (type_dechet,))
        prix_info = cur.fetchone()
        
        cur.execute("""
            SELECT reponse, conseil_pratique FROM chatbot_embeddings
            WHERE type_dechet = %s LIMIT 1
        """, (type_dechet,))
        connaissance = cur.fetchone()
        
        cur.execute("""
            SELECT nom, zone, arrondissement, fiabilite
            FROM points_collecte
            WHERE %s = ANY(types_dechets) OR 'tout' = ANY(types_dechets)
            ORDER BY CASE fiabilite WHEN 'officiel' THEN 1 WHEN 'enquete' THEN 2 
                     WHEN 'marche' THEN 3 WHEN 'genere' THEN 4 END
            LIMIT 5
        """, (type_dechet,))
        points = cur.fetchall()
    
    cur.close()
    conn.close()
    
    reponse = ""
    if connaissance:
        reponse = connaissance["reponse"]
    if prix_info:
        reponse += f"\n\nPrix : {prix_info['prix_kg']:.0f} FCFA/kg"
        reponse += f"\nSource : {prix_info['source']}"
    if points:
        reponse += "\n\nPoints de collecte :"
        for p in points[:3]:
            reponse += f"\n- {p['nom']} ({p['arrondissement']})"
    if not reponse:
        reponse = "Je n'ai pas compris. Parlez-moi d'un déchet (plastique, canette, verre...)"
    
    return {
        "langue_detectee": langue,
        "type_dechet": type_dechet,
        "reponse": reponse,
        "prix": prix_info,
        "points_collecte": points[:3]
    }

@app.post("/api/v1/chatbot/analyser-image")
async def chatbot_analyser_image(file: UploadFile = File(...)):
    """Analyse une image seule et renvoie la fiche associée."""
    image_bytes = await read_validated_image(file)
    
    type_dechet, confiance_type = predict_type(image_bytes)
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT reponse, conseil_pratique, detail_technique, impact_environnement,
               methode_valorisation, contact_douala, conseil_pratique
        FROM chatbot_embeddings
        WHERE type_dechet = %s LIMIT 1
    """, (type_dechet,))
    fiche = cur.fetchone()
    cur.close()
    conn.close()

    if not fiche:
        return {
            "type_detecte": type_dechet,
            "confiance_type": confiance_type,
            "reponse": "Déchet détecté, mais je n'ai pas encore d'information sur ce type."
        }

    return {
        "type_detecte": type_dechet,
        "confiance_type": confiance_type,
        "reponse": fiche["reponse"],
        "detail_technique": fiche["detail_technique"],
        "impact_environnement": fiche["impact_environnement"],
        "methode_valorisation": fiche["methode_valorisation"],
        "contact_douala": fiche["contact_douala"],
        "conseil_pratique": fiche["conseil_pratique"]
    }

@app.get("/api/v1/chatbot/point-proche")
def point_collecte_proche(lat: float, lon: float, type_dechet: str = None):
    """Retourne les points de collecte les plus proches d'une position GPS."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if type_dechet:
        cur.execute("""
            SELECT id, nom, type_activite, zone, arrondissement, contact,
                   ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
                   types_dechets, fiabilite, source,
                   ST_Distance(geometry, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) AS distance
            FROM points_collecte
            WHERE %s = ANY(types_dechets) OR 'tout' = ANY(types_dechets)
            ORDER BY distance
            LIMIT 5
        """, (lon, lat, type_dechet))
    else:
        cur.execute("""
            SELECT id, nom, type_activite, zone, arrondissement, contact,
                   ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
                   types_dechets, fiabilite, source,
                   ST_Distance(geometry, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) AS distance
            FROM points_collecte
            ORDER BY distance
            LIMIT 5
        """, (lon, lat))

    points = cur.fetchall()
    cur.close()
    conn.close()

    for p in points:
        p["distance_km"] = round(p["distance"] * 111, 2)

    return {"position": {"lat": lat, "lon": lon}, "points_proches": points}

# ================================================================
# COEUR DU CHATBOT (avec session, RAG hybride, ILIKE)
# ================================================================
def _process_chatbot_ask(
    question: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    image_bytes: Optional[bytes] = None,
    session_id: Optional[str] = None
):
    """
    Fonction commune : traitement de la question + option image + session.
    Avec intégration Redis (cache sémantique + mémoire de session).
    et reformulation humaine des réponses.
    """

    simple_response = simple_chat_response(question)
    if simple_response is not None:
        return simple_response
    if heavy_ai_disabled():
        language = detecter_langue(question)
        return {
            "langue": language,
            "source": "degraded",
            "intention": "waste_information",
            "reponse": "The waste assistant is temporarily unavailable." if language == "en" else "L’assistant déchets est temporairement indisponible.",
        }

    # ============================================================
    # 0. GESTION DE SESSION (mémoire)
    # ============================================================
    types_precedents = obtenir_types_precedents(session_id) if session_id else []
    memoire = obtenir_memoire_session(session_id) if session_id else []

    # Si une image est fournie, on enrichit la question
    if image_bytes:
        type_img, _ = predict_type(image_bytes)
        question = f"{question} {type_img}"

    langue = detecter_langue(question)
    question_normalisee = normaliser_et_corriger(question)
    question_lower = question_normalisee.lower()
    intention = detect_simple_intent(question_normalisee)
    cache_key = chatbot_cache_key(langue, intention, question_normalisee)

    # ============================================================
    # 1. VÉRIFICATION DU CACHE SÉMANTIQUE
    # ============================================================
    resultat_cache = obtenir_reponse_cachee(cache_key)
    if resultat_cache:
        # Si la question est en anglais et que le cache est en français, on traduit
        if langue == 'en' and resultat_cache.get("langue") == 'fr':
            resultat_cache["reponse"] = traduire_en_anglais(resultat_cache["reponse"])
        
        resultat_cache["source"] = "cache"
        resultat_cache["question_originale"] = question
        resultat_cache["langue"] = langue
        
        if session_id:
            ajouter_message_session(session_id, "user", question)
            ajouter_message_session(session_id, "assistant", resultat_cache.get("reponse", ""))
        
        return resultat_cache

    # Ajouter la question à la mémoire
    if session_id:
        ajouter_message_session(session_id, "user", question)


    # ============================================================
    # 2. DÉTECTION DE QUARTIER
    # ============================================================
    quartier_trouve = None
    mots_quartier = [m for m in question_normalisee.split() if len(m) > 3]
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    for mot in mots_quartier:
        cur.execute("""
            SELECT nom_quartier, ST_Y(geometry) AS lat, ST_X(geometry) AS lon
            FROM quartiers_douala
            WHERE nom_quartier ILIKE %s
            LIMIT 1
        """, (f'%{mot}%',))
        result = cur.fetchone()
        if result:
            quartier_trouve = result
            break
    cur.close()
    conn.close()

    # ============================================================
    # 3. FAQ MODULE (recherche BM25)
    # ============================================================
    if not quartier_trouve:
        faq_results = recherche_bm25(question_normalisee, top_k=1)
        if faq_results and faq_results[0]["score"] > FAQ_RELEVANCE_THRESHOLD:
            faq = faq_results[0]
            if langue == 'en':
                reponse_faq = traduire_en_anglais(faq["reponse"])
            else:
                reponse_faq = faq["reponse"]
            
            # Reformulation humaine
            resultat_brut = {"reponse": reponse_faq, "question": faq["question"]}
            reponse_humaine = formuler_reponse_humaine(resultat_brut, langue)
            
            resultat = {
                "langue": langue,
                "source": "faq",
                "question": faq["question"],
                "reponse": reponse_humaine,
                "score": faq["score"]
            }
            
            enregistrer_reponse_cachee(cache_key, resultat)
            if session_id:
                ajouter_message_session(session_id, "assistant", reponse_humaine)
            
            return resultat

    # ============================================================
    # 4. DÉTECTION DU TYPE DE DÉCHET (multi-déchets)
    # ============================================================
    phrases = segmenter_phrases(question)
    MOTS_GENERIQUES = {'jeter', 'poubelle', 'dechet', 'trash', 'waste', 'throw'}
    types_detectes = []
    
    for phrase in phrases:
        phrase_normalisee = normaliser_et_corriger(phrase)
        for mot in phrase_normalisee.split():
            if mot == 'can' and 'canette' not in phrase_normalisee:
                if any(m in phrase_normalisee for m in ['recycle', 'waste', 'jeter', 'throw', 'dispose']):
                    types_detectes.append('metal')
                    continue
            if mot in MAPPING_DECHETS:
                type_dech = MAPPING_DECHETS[mot]
                if mot in MOTS_GENERIQUES and types_detectes:
                    continue
                if type_dech not in types_detectes:
                    types_detectes.append(type_dech)

    # Fallback sur la session si aucun type détecté
    contexte_session = False
    if not types_detectes and types_precedents:
        types_detectes = types_precedents
        contexte_session = True

    # ============================================================
    # 5. CAS 1 : QUARTIER DÉTECTÉ → POINTS DE COLLECTE
    # ============================================================
    if quartier_trouve:
        points_result = point_collecte_proche(quartier_trouve["lat"], quartier_trouve["lon"])
        
        if types_detectes:
            reponses_combinees = []
            for type_dech in types_detectes:
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT type_dechet, reponse, detail_technique,
                           impact_environnement, methode_valorisation,
                           contact_douala, conseil_pratique
                    FROM chatbot_embeddings
                    WHERE type_dechet = %s LIMIT 1
                """, (type_dech,))
                fiche = cur.fetchone()
                cur.close()
                conn.close()
                if fiche:
                    reponses_combinees.append({
                        "type_dechet": fiche["type_dechet"],
                        "reponse": fiche["reponse"],
                        "detail_technique": fiche["detail_technique"],
                        "impact_environnement": fiche["impact_environnement"],
                        "methode_valorisation": fiche["methode_valorisation"],
                        "contact_douala": fiche["contact_douala"],
                        "conseil_pratique": fiche["conseil_pratique"],
                    })
            
            # Reformulation humaine combinée
            if reponses_combinees:
                reponse_globale = "\n\n".join([f"**{r['type_dechet']}** : {r['reponse']}" for r in reponses_combinees])
                resultat_brut = {
                    "reponse": reponse_globale,
                    "points_proches": points_result["points_proches"],
                    "type_dechet": reponses_combinees[0]["type_dechet"] if len(reponses_combinees)==1 else None,
                    "detail_technique": reponses_combinees[0].get("detail_technique") if len(reponses_combinees)==1 else None,
                    "impact_environnement": reponses_combinees[0].get("impact_environnement") if len(reponses_combinees)==1 else None,
                    "methode_valorisation": reponses_combinees[0].get("methode_valorisation") if len(reponses_combinees)==1 else None,
                    "contact_douala": reponses_combinees[0].get("contact_douala") if len(reponses_combinees)==1 else None,
                    "conseil_pratique": reponses_combinees[0].get("conseil_pratique") if len(reponses_combinees)==1 else None,
                }
                reponse_finale = formuler_reponse_humaine(resultat_brut, langue)
            else:
                reponse_finale = "Je n'ai pas trouvé de fiche pour ces déchets."
            
            if langue == 'en':
                reponse_finale = traduire_en_anglais(reponse_finale)
            
            resultat = {
                "langue": langue,
                "question_originale": question,
                "question_normalisee": question_normalisee,
                "types_detectes": types_detectes,
                "reponses": reponses_combinees,
                "reponse_globale": reponse_finale,
                "points_proches": points_result["points_proches"],
                "quartier": quartier_trouve["nom_quartier"],
                "contexte_session": contexte_session,
                **({"message_contexte": f"Réponse basée sur le contexte précédent : {', '.join(types_precedents)}"} if contexte_session else {})
            }
            
            enregistrer_reponse_cachee(cache_key, resultat)
            if session_id:
                ajouter_message_session(session_id, "assistant", reponse_finale, type_dechets=types_detectes)
            
            return resultat
        
        # Point proche seul
        resultat_brut = {
            "points_proches": points_result["points_proches"],
            "quartier": quartier_trouve["nom_quartier"]
        }
        reponse_humaine = formuler_reponse_humaine(resultat_brut, langue)
        
        resultat = {
            "langue": langue,
            "question_originale": question,
            "question_normalisee": question_normalisee,
            "points_proches": points_result["points_proches"],
            "quartier": quartier_trouve["nom_quartier"],
            "reponse": reponse_humaine,
            "message": f"Points de collecte près de {quartier_trouve['nom_quartier']}"
        }
        if session_id:
            ajouter_message_session(session_id, "assistant", reponse_humaine)
        return resultat

    # ============================================================
    # 6. CAS 2 : INTENTION DE PROXIMITÉ AVEC COORDONNÉES
    # ============================================================
    intention_proximite = any(mot in question_lower for mot in [
        'point de collecte', 'le plus proche', 'proche de moi', 'autour de moi',
        'où jeter', 'ou jeter', 'point de dépôt', 'collecte proche',
        'collection point', 'collection points', 'recycling point', 'drop-off',
        'near', 'around', 'close', 'nearby', 'where to dispose', 'disposal point',
        'collect', 'collection', 'nearest', 'closest'
    ])
    if intention_proximite and lat is not None and lon is not None:
        resultat = point_collecte_proche(lat, lon)
        reponse_humaine = formuler_reponse_humaine(resultat, langue)
        resultat["reponse"] = reponse_humaine
        enregistrer_reponse_cachee(cache_key, resultat)
        if session_id:
            ajouter_message_session(session_id, "assistant", reponse_humaine)
        return resultat

    # ============================================================
    # 7. CAS 3 : TYPE DE DÉCHET DÉTECTÉ → FICHE
    # ============================================================
    if types_detectes:
        reponses_combinees = []
        for type_dech in types_detectes:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT type_dechet, reponse, detail_technique,
                       impact_environnement, methode_valorisation,
                       contact_douala, conseil_pratique
                FROM chatbot_embeddings
                WHERE type_dechet = %s LIMIT 1
            """, (type_dech,))
            fiche = cur.fetchone()
            cur.close()
            conn.close()
            if fiche:
                reponses_combinees.append({
                    "type_dechet": fiche["type_dechet"],
                    "reponse": fiche["reponse"],
                    "detail_technique": fiche["detail_technique"],
                    "impact_environnement": fiche["impact_environnement"],
                    "methode_valorisation": fiche["methode_valorisation"],
                    "contact_douala": fiche["contact_douala"],
                    "conseil_pratique": fiche["conseil_pratique"],
                })
        if reponses_combinees:
            # Reformulation humaine
            reponse_globale = "\n\n".join([f"**{r['type_dechet']}** : {r['reponse']}" for r in reponses_combinees])
            resultat_brut = {
                "reponse": reponse_globale,
                "type_dechet": reponses_combinees[0]["type_dechet"] if len(reponses_combinees)==1 else None,
                "detail_technique": reponses_combinees[0].get("detail_technique") if len(reponses_combinees)==1 else None,
                "impact_environnement": reponses_combinees[0].get("impact_environnement") if len(reponses_combinees)==1 else None,
                "methode_valorisation": reponses_combinees[0].get("methode_valorisation") if len(reponses_combinees)==1 else None,
                "contact_douala": reponses_combinees[0].get("contact_douala") if len(reponses_combinees)==1 else None,
                "conseil_pratique": reponses_combinees[0].get("conseil_pratique") if len(reponses_combinees)==1 else None,
            }
            reponse_finale = formuler_reponse_humaine(resultat_brut, langue)
            
            if langue == 'en':
                reponse_finale = traduire_en_anglais(reponse_finale)
            
            resultat = {
                "langue": langue,
                "question_originale": question,
                "question_normalisee": question_normalisee,
                "types_detectes": types_detectes,
                "reponses": reponses_combinees,
                "reponse_globale": reponse_finale,
                "contexte_session": contexte_session,
                **({"message_contexte": f"Réponse basée sur le contexte précédent : {', '.join(types_precedents)}"} if contexte_session else {})
            }
            
            enregistrer_reponse_cachee(cache_key, resultat)
            if session_id:
                ajouter_message_session(session_id, "assistant", reponse_finale, type_dechets=types_detectes)
            
            return resultat

    # ============================================================
    # 8. CAS 4 : SALUTATIONS
    # ============================================================
    salutations = [
        'bonjour', 'bonsoir', 'salut', 'hello', 'good morning', 'goodmorning',
        'good evening', 'goodevening', 'morning', 'evening', 'on dit quoi',
        'bjr', 'bsr', 'hi', 'hey', 'coucou', 'yo', 'wesh', 'salam'
    ]
    if any(s in question_lower for s in salutations):
        if langue == 'en':
            reponse = "Hello! I'm SmartWaste Assistant. Ask me how to recycle or where to sell your waste in Douala."
        else:
            reponse = "Bonjour ! Je suis SmartWaste Assistant. Demandez-moi comment recycler ou où vendre vos déchets à Douala."
        resultat = {"langue": langue, "question_originale": question, "reponse": reponse}
        enregistrer_reponse_cachee(cache_key, resultat)
        if session_id:
            ajouter_message_session(session_id, "assistant", reponse)
        return resultat

    # ============================================================
    # 9. CAS 5 : RAG HYBRIDE (question complexe ou ambiguë)
    # ============================================================
    if session_id and types_precedents and len(question.split()) < 5:
        question_contextualisee = f"L'utilisateur demande : {question}. Le sujet précédent était : {', '.join(types_precedents)}"
    else:
        question_contextualisee = question

    try:
        vector_results = recherche_vectorielle(question_normalisee, top_k=10)
        bm25_results = recherche_bm25(question_normalisee, top_k=10)
        
        if vector_results and bm25_results:
            fused_ids = reciprocal_rank_fusion(vector_results, bm25_results)
            fused_chunks = []
            for idx, _ in fused_ids[:10]:
                for v in vector_results:
                    if v.get('id') == idx:
                        fused_chunks.append(v)
                        break
                else:
                    for b in bm25_results:
                        if b.get('id') == idx:
                            fused_chunks.append(b)
                            break
            chunks = fused_chunks if fused_chunks else vector_results
        else:
            chunks = vector_results if vector_results else bm25_results
        
        if chunks:
            reranked = rerank(question_normalisee, chunks, top_k=5)
            reponse_llm = generer_reponse_avec_contexte(question_contextualisee, reranked)
            
            if reponse_llm and ("Je n'ai pas" in reponse_llm or len(reponse_llm) < 30):
                resultat = {
                    "langue": langue,
                    "question_originale": question,
                    "question_normalisee": question_normalisee,
                    "source": "rag_hybride",
                    "reponse": "Je n'ai pas bien compris votre question. Essayez de reformuler, par exemple :\n- 'Que faire avec une pile ?'\n- 'Où vendre le plastique ?'\n- 'Points de collecte à Bonaberi'",
                    "suggestions": [
                        "Que faire avec une pile usagée ?",
                        "Où vendre le plastique à Douala ?",
                        "Points de collecte à Bonaberi"
                    ]
                }
                enregistrer_reponse_cachee(cache_key, resultat)
                if session_id:
                    ajouter_message_session(session_id, "assistant", resultat["reponse"])
                return resultat
            
            # Traduction en anglais si nécessaire
            if langue == 'en' and reponse_llm:
                reponse_llm = traduire_en_anglais(reponse_llm)
            
            resultat = {
                "langue": langue,
                "question_originale": question,
                "question_normalisee": question_normalisee,
                "source": "rag_hybride",
                "reponse": reponse_llm,
                "chunks_utilises": len(reranked)
            }
            
            enregistrer_reponse_cachee(cache_key, resultat)
            if session_id:
                ajouter_message_session(session_id, "assistant", reponse_llm)
            
            return resultat
    except Exception as e:
        pass

    # ============================================================
    # 10. FALLBACK : RAG simple
    # ============================================================
    try:
        q_emb = generer_embedding(question_normalisee)
        fiches = recherche_rag(q_emb, top_k=1)
    except Exception:
        fiches = []
    if fiches:
        fiche = fiches[0]
        sim = fiche["similarite"]
        if sim >= 0.6:
            resultat_brut = {
                "reponse": fiche["reponse"],
                "type_dechet": fiche["type_dechet"],
                "detail_technique": fiche["detail_technique"],
                "impact_environnement": fiche["impact_environnement"],
                "methode_valorisation": fiche["methode_valorisation"],
                "contact_douala": fiche["contact_douala"],
                "conseil_pratique": fiche["conseil_pratique"]
            }
            reponse = formuler_reponse_humaine(resultat_brut, langue)
            if langue == 'en':
                reponse = traduire_en_anglais(reponse)
            resultat = {
                "langue": langue,
                "question_originale": question,
                "question_normalisee": question_normalisee,
                "type_dechet": fiche["type_dechet"],
                "similarite": sim,
                "reponse": reponse,
                "detail_technique": fiche["detail_technique"],
                "impact_environnement": fiche["impact_environnement"],
                "methode_valorisation": fiche["methode_valorisation"],
                "contact_douala": fiche["contact_douala"],
                "conseil_pratique": fiche["conseil_pratique"],
            }
            enregistrer_reponse_cachee(cache_key, resultat)
            if session_id:
                ajouter_message_session(session_id, "assistant", reponse, type_dechets=[fiche["type_dechet"]])
            return resultat
        elif sim >= 0.4:
            contexte = construire_contexte(fiche, langue)
            if langue == 'en':
                reponse_llm = traduire_en_anglais(contexte)
                reponse_finale = reponse_llm
            else:
                reponse_llm = appeler_llm(question, contexte, langue)
                reponse_finale = verifier_reponse(reponse_llm, contexte)
            resultat = {
                "langue": langue,
                "question_originale": question,
                "question_normalisee": question_normalisee,
                "type_dechet": fiche["type_dechet"],
                "similarite": sim,
                "reponse": reponse_finale,
                "contact_douala": fiche["contact_douala"],
                "methode_valorisation": fiche["methode_valorisation"],
            }
            enregistrer_reponse_cachee(cache_key, resultat)
            if session_id:
                ajouter_message_session(session_id, "assistant", reponse_finale, type_dechets=[fiche["type_dechet"]])
            return resultat

    # ============================================================
    # 11. AUCUN RÉSULTAT
    # ============================================================
    if langue == 'en':
        reponse = "I don't have an answer for that yet. I can help with waste sorting, recycling, prices and collection points in Douala."
    else:
        reponse = "Je n'ai pas encore de réponse sur ce sujet. Je peux t'aider sur le tri, le recyclage, les prix et les points de collecte à Douala."
    
    resultat = {
        "langue": langue,
        "question_originale": question,
        "reponse": reponse,
        "suggestions": [
            "Que faire avec une pile usagée ?",
            "Où vendre le plastique à Douala ?",
            "Quelle société récupère le papier ?"
        ]
    }
    
    enregistrer_reponse_cachee(cache_key, resultat)
    if session_id:
        ajouter_message_session(session_id, "assistant", reponse)
    
    return resultat
# ================================================================
# ROUTES GET / POST pour /api/v1/chatbot/ask
# ================================================================
@app.get("/api/v1/chatbot/ask")
def chatbot_ask(
    question: str,
    session_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
):
    return _process_chatbot_ask(question, lat, lon, None, session_id)

@app.post("/api/v1/chatbot/ask")
async def chatbot_ask_post(
    question: str = Form(None),
    file: UploadFile = File(None),
    lat: float = Form(None),
    lon: float = Form(None),
    session_id: str = Form(None)
):
    """Version POST avec image et session."""
    image_bytes = await read_validated_image(file) if file else None
    return _process_chatbot_ask(question or "", lat, lon, image_bytes, session_id)

# ========== SUIVI AGENT (TEMPS RÉEL) ==========
@app.post("/api/v1/agent/position")
async def envoyer_position(
    lat: float,
    lon: float,
    user: dict = Depends(require_agent)
):
    if not is_agent_role(user.get("role", "")):
        raise HTTPException(403, "Réservé aux agents institutionnels")
    validate_coordinates(lat, lon)
    if not gps_rate_limiter.allow(user["user_id"]):
        raise HTTPException(429, "Mise à jour GPS trop fréquente")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM reports
        WHERE agent_id = %s AND status IN ('assigne', 'en_route', 'en_cours')
        LIMIT 1
        """,
        (user["user_id"],),
    )
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(409, "Aucune mission active")
    cur.execute("""
        INSERT INTO agent_positions (agent_id, lat, lon, timestamp)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (agent_id) DO UPDATE
        SET lat = EXCLUDED.lat, lon = EXCLUDED.lon, timestamp = NOW()
    """, (user["user_id"], lat, lon))
    conn.commit()
    cur.close()
    conn.close()

    import asyncio
    asyncio.create_task(ws_manager.send_to_managers({
        "type": "agent_position",
        "agent_id": user["user_id"],
        "lat": lat,
        "lon": lon
    }))

    return {"status": "ok", "lat": lat, "lon": lon}

@app.get("/api/v1/gestionnaire/agents-positions")
def get_agents_positions(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT agent_id, lat, lon, timestamp FROM agent_positions")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ========== OPTIMISATION TOURNÉES ==========
@app.get("/api/v1/tournees/optimiser")
def optimiser_tournee(
    arrondissement: str = None,
    max_signalements: int = 10,
    user: dict = Depends(require_admin)
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if arrondissement:
        cur.execute("""
            SELECT r.id, r.severity, r.confidence,
                   ST_Y(r.geometry) AS lat, ST_X(r.geometry) AS lon
            FROM reports r
            LEFT JOIN zones z ON ST_Contains(z.geometry, r.geometry)
            WHERE r.status IN ('soumis', 'valide', 'en_cours')
              AND r.severity IN ('critique', 'moderee')
              AND z.nom ILIKE %s
            ORDER BY CASE r.severity WHEN 'critique' THEN 1 WHEN 'moderee' THEN 2 END,
                     r.confidence DESC
            LIMIT %s
        """, (f'%{arrondissement}%', max_signalements))
    else:
        cur.execute("""
            SELECT r.id, r.severity, r.confidence,
                   ST_Y(r.geometry) AS lat, ST_X(r.geometry) AS lon
            FROM reports r
            WHERE r.status IN ('soumis', 'valide', 'en_cours')
              AND r.severity IN ('critique', 'moderee')
            ORDER BY CASE r.severity WHEN 'critique' THEN 1 WHEN 'moderee' THEN 2 END,
                     r.confidence DESC
            LIMIT %s
        """, (max_signalements,))
    signalements = cur.fetchall()
    cur.close()
    conn.close()
    if len(signalements) < 2:
        return {"message": "Pas assez de signalements", "tournee": []}
    def distance(p1, p2):
        import math
        return math.sqrt((p1["lat"] - p2["lat"])**2 + (p1["lon"] - p2["lon"])**2)
    depart = min(signalements, key=lambda s: s["lat"])
    tournee = [depart]
    non_visites = [s for s in signalements if s["id"] != depart["id"]]
    while non_visites:
        dernier = tournee[-1]
        prochain = min(non_visites, key=lambda s: distance(dernier, s))
        tournee.append(prochain)
        non_visites.remove(prochain)
    distance_km = round(sum(distance(tournee[i], tournee[i+1]) for i in range(len(tournee)-1)) * 111, 2)
    return {"message": "Tournée optimisée", "nb_signalements": len(tournee), "distance_estimee_km": distance_km, "tournee": tournee}

@app.get("/api/v1/tournees/optimiser-vrp")
def optimiser_tournee_vrp(
    arrondissement: str = None,
    nb_vehicules: int = 1,
    capacite_vehicule: int = 1000,
    max_signalements: int = 10,
    user: dict = Depends(require_admin)
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if arrondissement:
        cur.execute("""
            SELECT r.id, r.severity, r.confidence,
                   ST_Y(r.geometry) AS lat, ST_X(r.geometry) AS lon
            FROM reports r
            LEFT JOIN zones z ON ST_Contains(z.geometry, r.geometry)
            WHERE r.status IN ('soumis', 'valide', 'en_cours')
              AND r.severity IN ('critique', 'moderee')
              AND z.nom ILIKE %s
            ORDER BY CASE r.severity WHEN 'critique' THEN 1 ELSE 2 END,
                     r.confidence DESC
            LIMIT %s
        """, (f'%{arrondissement}%', max_signalements))
    else:
        cur.execute("""
            SELECT r.id, r.severity, r.confidence,
                   ST_Y(r.geometry) AS lat, ST_X(r.geometry) AS lon
            FROM reports r
            WHERE r.status IN ('soumis', 'valide', 'en_cours')
              AND r.severity IN ('critique', 'moderee')
            ORDER BY CASE r.severity WHEN 'critique' THEN 1 ELSE 2 END,
                     r.confidence DESC
            LIMIT %s
        """, (max_signalements,))
    signalements = cur.fetchall()
    cur.close()
    conn.close()
    if len(signalements) < 2:
        return {"message": "Pas assez de signalements", "tournee": []}
    depot = min(signalements, key=lambda s: s["lat"])
    points = [(depot["lat"], depot["lon"])] + [(s["lat"], s["lon"]) for s in signalements]
    try:
        matrice = calculer_matrice_distances(points)
    except Exception as e:
        return {"message": "Erreur OSMnx, optimisation glouton utilisée", "detail": str(e), "tournee": None}
    demandes = [0] + [1] * len(signalements)
    capacites = [capacite_vehicule] * nb_vehicules
    tournees = resoudre_vrp(matrice, nb_vehicules, capacites, demandes)
    if tournees is None:
        return {"message": "Aucune solution VRP trouvée"}
    resultats = []
    for idx, route in enumerate(tournees):
        ordre_visite = []
        compteur = 0
        for node in route:
            if node == 0:
                continue
            compteur += 1
            sig = signalements[node - 1]
            ordre_visite.append({"ordre": compteur, "id": sig["id"], "severity": sig["severity"], "lat": sig["lat"], "lon": sig["lon"]})
        if ordre_visite:
            resultats.append({"vehicule": idx + 1, "nb_points": len(ordre_visite), "tournee": ordre_visite})
    return {"message": "Tournée VRP optimisée", "arrondissement": arrondissement, "nb_vehicules": nb_vehicules, "tournees": resultats}

@app.post("/api/v1/tournees/creer")
def creer_tournee(payload: TourneeCreate, user: dict = Depends(require_admin)):
    agent_id = payload.agent_id
    signalement_ids = payload.signalement_ids
    date_planifiee = payload.date_planifiee

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        INSERT INTO tours (agent_id, planned_date, status)
        VALUES (%s, %s, 'planifiee')
        RETURNING id
    """, (agent_id, date_planifiee))
    tournee_id = cur.fetchone()["id"]

    for sid in signalement_ids:
        cur.execute("""
            UPDATE reports SET status = 'en_cours', tournee_id = %s, updated_at = NOW()
            WHERE id = %s AND status = 'valide'
        """, (tournee_id, sid))

    conn.commit()
    cur.close()
    conn.close()
    return {"tournee_id": tournee_id, "agent_id": agent_id, "nb_signalements": len(signalement_ids), "date_planifiee": date_planifiee}

@app.get("/api/v1/tournees/en-cours")
def tournees_en_cours(user: dict = Depends(require_agent)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.id, t.agent_id, u.arrondissement, t.status,
               t.planned_date, COUNT(r.id) AS nb_signalements
        FROM tours t
        LEFT JOIN users u ON u.id = t.agent_id
        LEFT JOIN reports r ON r.tournee_id = t.id
                WHERE t.status IN ('planifiee', 'en_cours')
                    AND (%s OR t.agent_id = %s)
        GROUP BY t.id, u.arrondissement
        ORDER BY t.planned_date DESC
        """, (is_manager_role(user["role"]), user["user_id"]))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.get("/api/v1/tournees/{tournee_id}/points")
def points_tournee(tournee_id: int, user: dict = Depends(require_agent)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, severity, confidence, status, waste_type,
               ST_Y(geometry) AS lat, ST_X(geometry) AS lon
        FROM reports
        WHERE tournee_id = %s
          AND (%s OR EXISTS (
              SELECT 1 FROM tours t
              WHERE t.id = reports.tournee_id AND t.agent_id = %s
          ))
        ORDER BY id
    """, (tournee_id, is_manager_role(user["role"]), user["user_id"]))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.get("/api/v1/tournees/{tournee_id}/itineraire")
def itineraire_tournee(tournee_id: int, user: dict = Depends(require_agent)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
               severity, status, waste_type
        FROM reports
        WHERE tournee_id = %s
          AND (%s OR EXISTS (
              SELECT 1 FROM tours t
              WHERE t.id = reports.tournee_id AND t.agent_id = %s
          ))
        ORDER BY id
    """, (tournee_id, is_manager_role(user["role"]), user["user_id"]))
    points = cur.fetchall()
    cur.close()
    conn.close()

    if not points:
        raise HTTPException(404, "Tournée non trouvée ou non assignée")
    if len(points) < 2:
        return {"points": points, "geometry": None}

    route = get_route([(p["lat"], p["lon"]) for p in points])
    if not route:
        return {"points": points, "geometry": None, "message": "Itinéraire temporairement indisponible"}
    return {"points": points, **route}

# ========== TERMINER UNE TOURNÉE ==========
@app.put("/api/v1/tournees/{tournee_id}/terminer")
def terminer_tournee(tournee_id: int, user: dict = Depends(require_agent)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE tours
        SET status = 'terminee', updated_at = NOW()
        WHERE id = %s AND agent_id = %s
        RETURNING id
    """, (tournee_id, user["user_id"]))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Tournée non trouvée ou non assignée")
    return {"message": "Tournée terminée"}

# ========== SUIVI CITOYEN & ABONNEMENTS ==========

@app.get("/api/v1/mes-signalements")
def get_mes_signalements(user: dict = Depends(require_auth)):
    """Liste tous les signalements du citoyen connecté."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, severity, confidence, status, waste_type,
               ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
               created_at, updated_at,
               agent_id,
               (SELECT email FROM users WHERE id = reports.agent_id) AS agent_email
        FROM reports
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user["user_id"],))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.get("/api/v1/signalements/{report_id}/suivi")
def get_suivi(report_id: int, user: dict = Depends(require_auth)):
    """Détail d’un signalement avec position de l’agent si assigné."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT r.id, r.status, r.severity, r.waste_type,
               r.created_at, r.updated_at,
               u.email AS agent_email,
               ap.lat AS agent_lat,
               ap.lon AS agent_lon,
               ap.timestamp AS agent_last_seen
        FROM reports r
        LEFT JOIN users u ON u.id = r.agent_id
        LEFT JOIN agent_positions ap ON ap.agent_id = u.id
        WHERE r.id = %s AND r.user_id = %s
    """, (report_id, user["user_id"]))
    result = cur.fetchone()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Signalement non trouvé ou non autorisé")
    return result

@app.put("/api/v1/signalements/{report_id}/assigner")
def assigner_agent(
    report_id: int,
    agent_id: int,
    user: dict = Depends(require_admin)
):
    """Le gestionnaire assigne un agent à un signalement validé."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reports
        SET agent_id = %s, status = 'en_cours', updated_at = NOW()
        WHERE id = %s AND status = 'valide'
        RETURNING id
    """, (agent_id, report_id))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(400, "Signalement non valide ou déjà assigné")
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Agent assigné"}

# ========== ABONNEMENTS (collecte régulière) ==========

class AbonnementCreate(BaseModel):
    lat: float
    lon: float
    frequence: str  # 'hebdo', 'bimensuel', 'mensuel'
    notes: Optional[str] = None

@app.post("/api/v1/abonnements")
def creer_abonnement(
    payload: AbonnementCreate,
    user: dict = Depends(require_auth)
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO abonnements_collecte
        (user_id, adresse_geometry, frequence, prochain_passage, notes)
        VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, NOW() + INTERVAL '7 days', %s)
        RETURNING id
    """, (user["user_id"], payload.lon, payload.lat, payload.frequence, payload.notes))
    abo_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": abo_id, "message": "Abonnement créé"}

@app.get("/api/v1/abonnements")
def get_abonnements(user: dict = Depends(require_admin)):
    """Liste tous les abonnements pour le gestionnaire."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT a.id, a.user_id, u.email, a.frequence, a.prochain_passage,
               a.actif, a.notes,
               ST_Y(a.adresse_geometry) AS lat, ST_X(a.adresse_geometry) AS lon
        FROM abonnements_collecte a
        JOIN users u ON u.id = a.user_id
        ORDER BY a.prochain_passage ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.get("/api/v1/abonnements/mes-abonnements")
def get_mes_abonnements(user: dict = Depends(require_auth)):
    """Liste des abonnements du citoyen connecté."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, frequence, prochain_passage, actif, notes,
               ST_Y(adresse_geometry) AS lat, ST_X(adresse_geometry) AS lon
        FROM abonnements_collecte
        WHERE user_id = %s
        ORDER BY prochain_passage ASC
    """, (user["user_id"],))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.get("/api/v1/stats")
def get_stats(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Total signalements
    cur.execute("SELECT COUNT(*) AS total FROM reports")
    total = cur.fetchone()["total"]

    # Par statut
    cur.execute("""
        SELECT status, COUNT(*) AS count
        FROM reports
        GROUP BY status
    """)
    par_statut = cur.fetchall()

    # Par sévérité
    cur.execute("""
        SELECT severity, COUNT(*) AS count
        FROM reports
        GROUP BY severity
    """)
    par_severite = cur.fetchall()

    # Agents actifs (sans table agent_positions si elle manque)
    try:
        cur.execute("""
            SELECT COUNT(DISTINCT agent_id) AS actifs
            FROM agent_positions
            WHERE timestamp > NOW() - INTERVAL '5 minutes'
        """)
        agents_actifs = cur.fetchone()["actifs"]
    except Exception:
        agents_actifs = 0

    cur.close()
    conn.close()

    return {
        "total": total,
        "par_statut": par_statut,
        "par_severite": par_severite,
        "par_arrondissement": [],  # simplifié pour éviter l'erreur de jointure
        "agents_actifs": agents_actifs
    }
@app.get("/api/v1/prix")
def get_prix(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, type_dechet, prix_kg, source, ville, date_maj FROM prix_reference ORDER BY type_dechet")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.put("/api/v1/prix/{prix_id}")
def update_prix(prix_id: int, prix_kg: float, user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE prix_reference
        SET prix_kg = %s, date_maj = NOW()
        WHERE id = %s
        RETURNING id
    """, (prix_kg, prix_id))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Prix non trouvé")
    return {"message": "Prix mis à jour"}

class PointCollecteCreate(BaseModel):
    nom: str
    type_activite: str = "Point de collecte"
    zone: str = None
    arrondissement: str = None
    lat: float
    lon: float
    types_dechets: List[str] = ["tout"]
    contact: str = None

@app.post("/api/v1/points-collecte")
def create_point_collecte(
    payload: PointCollecteCreate,
    user: dict = Depends(require_admin)
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO points_collecte
        (nom, type_activite, zone, arrondissement, geometry, types_dechets, contact, source, fiabilite)
        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, 'admin', 'officiel')
        RETURNING id
    """, (payload.nom, payload.type_activite, payload.zone, payload.arrondissement,
          payload.lon, payload.lat, payload.types_dechets, payload.contact))
    point_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": point_id, "message": "Point de collecte ajouté"}

@app.put("/api/v1/points-collecte/{point_id}")
def update_point_collecte(
    point_id: int,
    payload: PointCollecteCreate,
    user: dict = Depends(require_admin)
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE points_collecte
        SET nom = %s, type_activite = %s, zone = %s, arrondissement = %s,
            geometry = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
            types_dechets = %s, contact = %s
        WHERE id = %s
        RETURNING id
    """, (payload.nom, payload.type_activite, payload.zone, payload.arrondissement,
          payload.lon, payload.lat, payload.types_dechets, payload.contact, point_id))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Point non trouvé")
    return {"message": "Point de collecte mis à jour"}

@app.delete("/api/v1/points-collecte/{point_id}")
def delete_point_collecte(point_id: int, user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM points_collecte WHERE id = %s RETURNING id", (point_id,))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Point non trouvé")
    return {"message": "Point de collecte supprimé"}

@app.get("/api/v1/users")
def get_users(role: str = None, user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if role:
        cur.execute("""
            SELECT id, email, role, arrondissement, created_at
            FROM users
            WHERE role = %s
            ORDER BY id
        """, (role,))
    else:
        cur.execute("SELECT id, email, role, arrondissement, created_at FROM users ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.delete("/api/v1/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s AND role != 'admin' RETURNING id", (user_id,))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(404, "Utilisateur non trouvé ou admin")
    return {"message": "Utilisateur supprimé"}

@app.get("/api/v1/stats/avancees")
def stats_avancees(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Temps moyen de traitement (secondes)
    cur.execute("""
        SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) AS temps_moyen_secondes
        FROM reports WHERE status = 'traite'
    """)
    temps_moyen = cur.fetchone()["temps_moyen_secondes"]

    # Taux de résolution
    cur.execute("SELECT COUNT(*) AS total FROM reports")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS resolus FROM reports WHERE status = 'traite'")
    resolus = cur.fetchone()["resolus"]
    taux = (resolus / total * 100) if total > 0 else 0

    # Volume estimé (poids moyen par type)
    poids_moyens = {
        "plastic": 1.5, "metal": 2.0, "glass": 1.0, "paper": 0.8,
        "cardboard": 1.2, "biological": 0.5, "clothes": 0.4, "shoes": 0.3,
        "battery": 0.2, "trash": 1.0, "brown-glass": 1.0,
        "green-glass": 1.0, "white-glass": 1.0
    }
    cur.execute("""SELECT waste_type, COUNT(*) AS nb FROM reports
                   WHERE status IN ('traite','valide','en_cours')
                   GROUP BY waste_type""")
    volume_estime = 0
    for row in cur.fetchall():
        volume_estime += poids_moyens.get(row["waste_type"], 1.0) * row["nb"]

    # Top 5 zones critiques
    cur.execute("""
        SELECT z.nom AS zone, COUNT(r.id) AS nb
        FROM reports r
        LEFT JOIN zones z ON ST_Contains(z.geometry, r.geometry)
        WHERE r.status NOT IN ('refuse', 'rejete_hors_sujet')
        GROUP BY z.nom
        ORDER BY nb DESC
        LIMIT 5
    """)
    top_zones = cur.fetchall()

    cur.close(); conn.close()
    return {
        "temps_moyen_traitement_secondes": round(temps_moyen, 1) if temps_moyen else None,
        "taux_resolution_pourcent": round(taux, 1),
        "volume_estime_kg": round(volume_estime, 1),
        "top_zones_critiques": top_zones
    }

@app.get("/api/v1/stats/evolution")
def stats_evolution(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DATE(created_at) AS jour, COUNT(*) AS nb
        FROM reports
        GROUP BY DATE(created_at)
        ORDER BY jour
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"date": r["jour"].isoformat(), "count": r["nb"]} for r in rows]

@app.get("/api/v1/export/signalements.csv")
def export_signalements_csv(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT id, severity, confidence, status, waste_type,
                   ST_Y(geometry) AS lat, ST_X(geometry) AS lon,
                   created_at, updated_at
                   FROM reports ORDER BY created_at DESC""")
    rows = cur.fetchall()
    cur.close(); conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","severity","confidence","status","waste_type","lat","lon","created_at","updated_at"])
    for r in rows:
        writer.writerow([r["id"], r["severity"], r["confidence"], r["status"], r["waste_type"], r["lat"], r["lon"], r["created_at"], r["updated_at"]])
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=signalements.csv"})

@app.get("/api/v1/export/tournees.csv")
def export_tournees_csv(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT t.id, t.agent_id, t.status, t.planned_date, u.arrondissement,
                   COUNT(r.id) AS nb_signalements
                   FROM tours t
                   LEFT JOIN users u ON u.id = t.agent_id
                   LEFT JOIN reports r ON r.tournee_id = t.id
                   GROUP BY t.id, u.arrondissement
                   ORDER BY t.planned_date DESC""")
    rows = cur.fetchall(); cur.close(); conn.close()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["id","agent_id","status","planned_date","arrondissement","nb_signalements"])
    for r in rows:
        writer.writerow([r["id"], r["agent_id"], r["status"], r["planned_date"], r["arrondissement"], r["nb_signalements"]])
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=tournees.csv"})

@app.get("/api/v1/tournees/historique")
def historique_tournees(user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT id, agent_id, status, planned_date, created_at
                   FROM tours WHERE status IN ('terminee','annulee')
                   ORDER BY planned_date DESC""")
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

@app.get("/api/v1/tournees/{tournee_id}/details")
def details_tournee(tournee_id: int, user: dict = Depends(require_admin)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tours WHERE id=%s", (tournee_id,))
    tour = cur.fetchone()
    if not tour:
        raise HTTPException(404, "Tournée non trouvée")
    cur.execute("""SELECT id, severity, status, waste_type,
                   ST_Y(geometry) AS lat, ST_X(geometry) AS lon
                   FROM reports WHERE tournee_id=%s ORDER BY id""", (tournee_id,))
    points = cur.fetchall()
    cur.close(); conn.close()
    return {"tournee": tour, "points": points}

