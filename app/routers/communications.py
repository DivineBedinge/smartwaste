import base64
import os
import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from psycopg2.extras import Json, RealDictCursor

from app.services.notifications import create_notification
from app.services.uploads import read_validated_image
from core.policy import is_manager_role
from core.security import decode_token
from database import get_db_connection

router = APIRouter(prefix="/api/v1", tags=["communications"])
security = HTTPBearer()


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Token invalide ou expiré")
    return payload


def manager(user=Depends(current_user)):
    if not is_manager_role(user.get("role", "")):
        raise HTTPException(403, "Réservé aux gestionnaires")
    return user


class ConversationCreate(BaseModel):
    resource_type: str
    resource_id: int = Field(ge=1)


class CallbackCreate(BaseModel):
    resource_type: Optional[str] = None
    resource_id: Optional[int] = Field(default=None, ge=1)
    preferred_at: Optional[datetime] = None
    reason: str = Field(min_length=2, max_length=500)


class CallbackStatus(BaseModel):
    status: str


class AbuseReport(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


def eligible_users(cur, resource_type: str, resource_id: int) -> set[int]:
    if resource_type == "report":
        cur.execute("SELECT user_id,agent_id FROM reports WHERE id=%s", (resource_id,))
    elif resource_type == "collection":
        cur.execute(
            """SELECT s.user_id,o.collector_id
               FROM collection_occurrences o
               JOIN domestic_subscriptions s ON s.id=o.subscription_id
               WHERE o.id=%s
                 AND o.status IN ('affectee','en_route','arrivee')""",
            (resource_id,),
        )
    elif resource_type == "tour":
        cur.execute("SELECT agent_id,NULL FROM tours WHERE id=%s", (resource_id,))
    elif resource_type == "support":
        cur.execute("SELECT author_id,assigned_to FROM support_requests WHERE id=%s", (resource_id,))
    else:
        raise HTTPException(422, "Type de ressource invalide")
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Ressource non trouvée")
    users = {value for value in row if value is not None}
    cur.execute("SELECT id FROM users WHERE role IN ('gestionnaire','admin','municipal') AND active=TRUE")
    users.update(value[0] for value in cur.fetchall())
    return users


def require_participant(cur, conversation_id: int, user_id: int, lock=False):
    query = "SELECT status,resource_type,resource_id FROM conversations WHERE id=%s"
    if lock:
        query += " FOR UPDATE"
    cur.execute(query, (conversation_id,))
    conversation = cur.fetchone()
    if not conversation:
        raise HTTPException(404, "Conversation non trouvée")
    cur.execute("SELECT 1 FROM conversation_participants WHERE conversation_id=%s AND user_id=%s", (conversation_id, user_id))
    if not cur.fetchone():
        raise HTTPException(404, "Conversation non trouvée")
    return conversation


@router.post("/conversations")
def get_or_create_conversation(payload: ConversationCreate, user=Depends(current_user)):
    conn=get_db_connection(); cur=conn.cursor()
    users=eligible_users(cur,payload.resource_type,payload.resource_id)
    if user["user_id"] not in users:
        cur.close(); conn.close(); raise HTTPException(403,"Accès refusé à cette ressource")
    cur.execute("INSERT INTO conversations(resource_type,resource_id,created_by) VALUES (%s,%s,%s) ON CONFLICT(resource_type,resource_id) DO UPDATE SET resource_id=EXCLUDED.resource_id RETURNING id,status",(payload.resource_type,payload.resource_id,user["user_id"]))
    conversation_id,status=cur.fetchone()
    cur.executemany("INSERT INTO conversation_participants(conversation_id,user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",[(conversation_id,uid) for uid in users])
    conn.commit(); cur.close(); conn.close()
    return {"id":conversation_id,"status":status,"resource_type":payload.resource_type,"resource_id":payload.resource_id}


@router.get("/conversations")
def list_conversations(limit:int=20,offset:int=0,user=Depends(current_user)):
    if limit<1 or limit>100 or offset<0: raise HTTPException(422,"Pagination invalide")
    conn=get_db_connection(); cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT c.id,c.resource_type,c.resource_id,c.status,c.created_at,
        (SELECT ARRAY_AGG(DISTINCT u.role ORDER BY u.role) FROM conversation_participants cp JOIN users u ON u.id=cp.user_id WHERE cp.conversation_id=c.id) AS participant_roles,
        (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id AND m.sender_id<>%s AND m.created_at>COALESCE((SELECT last_read_at FROM conversation_reads r WHERE r.conversation_id=c.id AND r.user_id=%s),'-infinity')) AS unread_count
        FROM conversations c JOIN conversation_participants p ON p.conversation_id=c.id WHERE p.user_id=%s
        ORDER BY c.created_at DESC,c.id DESC LIMIT %s OFFSET %s""",(user["user_id"],user["user_id"],user["user_id"],limit,offset))
    rows=cur.fetchall(); cur.close(); conn.close(); return rows


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id:int,limit:int=30,offset:int=0,user=Depends(current_user)):
    if limit<1 or limit>100 or offset<0: raise HTTPException(422,"Pagination invalide")
    conn=get_db_connection(); cur=conn.cursor(cursor_factory=RealDictCursor); require_participant(cur,conversation_id,user["user_id"])
    cur.execute("""SELECT m.id,m.sender_id,m.client_id,m.message_type,m.body,m.attachment_mime,
        (m.attachment_base64 IS NOT NULL) AS has_attachment,m.created_at,u.role AS sender_role
        FROM messages m LEFT JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=%s
        ORDER BY m.created_at DESC,m.id DESC LIMIT %s OFFSET %s""",(conversation_id,limit,offset)); rows=cur.fetchall(); cur.close(); conn.close(); return rows


@router.get("/messages/{message_id}/attachment")
def get_message_attachment(message_id:int,user=Depends(current_user)):
    conn=get_db_connection(); cur=conn.cursor()
    cur.execute("SELECT conversation_id,attachment_base64,attachment_mime FROM messages WHERE id=%s",(message_id,)); row=cur.fetchone()
    if not row or not row[1]: cur.close(); conn.close(); raise HTTPException(404,"Pièce jointe non trouvée")
    require_participant(cur,row[0],user["user_id"])
    content=base64.b64decode(row[1],validate=True); mime=row[2]
    if mime not in {"image/jpeg","image/png","image/webp"}: cur.close(); conn.close(); raise HTTPException(415,"Type de pièce jointe invalide")
    cur.close(); conn.close(); return Response(content=content,media_type=mime,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id:int,client_id:str=Form(...),body:Optional[str]=Form(None),file:Optional[UploadFile]=File(None),user=Depends(current_user)):
    try: client_uuid=UUID(client_id)
    except ValueError as exc: raise HTTPException(422,"client_id invalide") from exc
    text=(body or "").strip()
    if len(text)>5000 or (not text and not file): raise HTTPException(422,"Message vide ou trop long")
    attachment=None; mime=None
    if file:
        content=await read_validated_image(file); attachment=base64.b64encode(content).decode("ascii"); mime=file.content_type
    conn=get_db_connection(); cur=conn.cursor(); conversation=require_participant(cur,conversation_id,user["user_id"],lock=True)
    if conversation[0]!="open": cur.close(); conn.close(); raise HTTPException(409,"Conversation clôturée")
    cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=%s AND sender_id=%s AND created_at>NOW()-INTERVAL '1 minute'",(conversation_id,user["user_id"]))
    if cur.fetchone()[0]>=30: cur.close(); conn.close(); raise HTTPException(429,"Trop de messages")
    cur.execute("INSERT INTO messages(conversation_id,sender_id,client_id,message_type,body,attachment_base64,attachment_mime) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(conversation_id,client_id) DO UPDATE SET client_id=EXCLUDED.client_id RETURNING id,created_at",(conversation_id,user["user_id"],str(client_uuid),"image" if attachment else "text",text or None,attachment,mime)); message_id,created_at=cur.fetchone()
    cur.execute("SELECT user_id FROM conversation_participants WHERE conversation_id=%s AND user_id<>%s",(conversation_id,user["user_id"]))
    for (recipient,) in cur.fetchall():
        create_notification(conn,recipient,"new_message","Nouveau message","Un nouveau message contextuel est disponible.",None,"notification.new_message",{"conversation_id":conversation_id},resource_type="conversation",resource_id=conversation_id,idempotency_key=client_uuid)
    conn.commit(); cur.close(); conn.close(); return {"id":message_id,"client_id":client_id,"status":"sent","created_at":created_at}


@router.patch("/conversations/{conversation_id}/read")
def read_conversation(conversation_id:int,user=Depends(current_user)):
    conn=get_db_connection(); cur=conn.cursor(); require_participant(cur,conversation_id,user["user_id"]); cur.execute("INSERT INTO conversation_reads(conversation_id,user_id,last_read_at) VALUES (%s,%s,NOW()) ON CONFLICT(conversation_id,user_id) DO UPDATE SET last_read_at=NOW()",(conversation_id,user["user_id"])); conn.commit(); cur.close(); conn.close(); return {"read":True}


@router.patch("/conversations/{conversation_id}/close")
def close_conversation(conversation_id:int,user=Depends(current_user)):
    conn=get_db_connection(); cur=conn.cursor(); require_participant(cur,conversation_id,user["user_id"],lock=True); cur.execute("UPDATE conversations SET status='closed',closed_at=NOW() WHERE id=%s RETURNING id",(conversation_id,))
    cur.execute("SELECT user_id FROM conversation_participants WHERE conversation_id=%s AND user_id<>%s",(conversation_id,user["user_id"]))
    for (recipient,) in cur.fetchall():
        create_notification(conn,recipient,"conversation_closed","Conversation clôturée","Une conversation contextuelle a été clôturée.",None,"notification.conversation_closed",{"conversation_id":conversation_id},resource_type="conversation",resource_id=conversation_id)
    conn.commit(); cur.close(); conn.close(); return {"id":conversation_id,"status":"closed"}


@router.post("/messages/{message_id}/report")
def report_message(message_id:int,payload:AbuseReport,user=Depends(current_user)):
    conn=get_db_connection(); cur=conn.cursor(); cur.execute("SELECT conversation_id FROM messages WHERE id=%s",(message_id,)); row=cur.fetchone()
    if not row: cur.close(); conn.close(); raise HTTPException(404,"Message non trouvé")
    require_participant(cur,row[0],user["user_id"]); cur.execute("INSERT INTO message_reports(message_id,reporter_id,reason) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id",(message_id,user["user_id"],payload.reason)); result=cur.fetchone()
    if result:
        cur.execute("SELECT id FROM users WHERE role IN ('gestionnaire','admin','municipal') AND active=TRUE")
        for (recipient,) in cur.fetchall():
            create_notification(conn,recipient,"message_reported","Message signalé","Un message contextuel a été signalé.","/gestionnaire#conversations","notification.message_reported",{"conversation_id":row[0]},resource_type="conversation",resource_id=row[0])
    conn.commit(); cur.close(); conn.close(); return {"reported":bool(result)}


@router.post("/callback-requests")
def request_callback(payload:CallbackCreate,user=Depends(current_user)):
    if (payload.resource_type is None) != (payload.resource_id is None):
        raise HTTPException(422, "La ressource et son identifiant doivent être fournis ensemble")
    conn=get_db_connection(); cur=conn.cursor()
    if payload.resource_type is not None:
        users = eligible_users(cur, payload.resource_type, payload.resource_id)
        if user["user_id"] not in users:
            cur.close(); conn.close(); raise HTTPException(403, "Accès refusé à cette ressource")
    cur.execute("INSERT INTO callback_requests(requester_id,resource_type,resource_id,preferred_at,reason) VALUES (%s,%s,%s,%s,%s) RETURNING id,status,created_at",(user["user_id"],payload.resource_type,payload.resource_id,payload.preferred_at,payload.reason)); result=cur.fetchone(); cur.execute("SELECT id FROM users WHERE role IN ('gestionnaire','admin','municipal') AND active=TRUE")
    for (recipient,) in cur.fetchall(): create_notification(conn,recipient,"callback_requested","Demande de rappel","Une nouvelle demande de rappel est disponible.","/gestionnaire#callbacks","notification.callback_requested",{"callback_id":result[0]},resource_type="callback",resource_id=result[0])
    conn.commit(); cur.close(); conn.close(); return {"id":result[0],"status":result[1],"created_at":result[2]}


@router.get("/callback-requests")
def list_callbacks(user=Depends(current_user)):
    conn=get_db_connection(); cur=conn.cursor(cursor_factory=RealDictCursor)
    if is_manager_role(user["role"]): cur.execute("SELECT * FROM callback_requests ORDER BY created_at DESC LIMIT 100")
    else: cur.execute("SELECT * FROM callback_requests WHERE requester_id=%s ORDER BY created_at DESC LIMIT 100",(user["user_id"],))
    rows=cur.fetchall(); cur.close(); conn.close(); return rows


@router.patch("/callback-requests/{callback_id}/status")
def update_callback(callback_id:int,payload:CallbackStatus,user=Depends(manager)):
    if payload.status not in {"scheduled","completed","cancelled"}: raise HTTPException(422,"Statut invalide")
    conn=get_db_connection(); cur=conn.cursor(); cur.execute("UPDATE callback_requests SET status=%s,updated_at=NOW() WHERE id=%s RETURNING requester_id",(payload.status,callback_id)); row=cur.fetchone()
    if not row: cur.close(); conn.close(); raise HTTPException(404,"Demande introuvable")
    create_notification(conn,row[0],"callback_status","Demande de rappel mise à jour","Votre demande de rappel a été mise à jour.",None,"notification.callback_status",{"callback_id":callback_id,"status":payload.status},resource_type="callback",resource_id=callback_id); conn.commit(); cur.close(); conn.close(); return {"id":callback_id,"status":payload.status}


@router.get("/support-phone")
def support_phone(user=Depends(current_user)):
    number=os.getenv("SUPPORT_PHONE","").strip()
    if not number: return {"available":False,"href":None}
    if not re.fullmatch(r"\+?[1-9][0-9]{7,14}",number): raise HTTPException(503,"Numéro de support invalide")
    conn=get_db_connection(); cur=conn.cursor()
    cur.execute(
        "INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,new_value) VALUES (%s,%s,'support_phone_opened','support',%s)",
        (user["user_id"], user["role"], Json({"configured_support_number": True})),
    )
    conn.commit(); cur.close(); conn.close()
    return {"available":True,"href":f"tel:{number}"}
