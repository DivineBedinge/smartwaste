import base64
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg2.extras import RealDictCursor

from app.services.media_assets import store_media_with_compensation
from app.services.media_storage import get_media_storage
from app.services.uploads import read_validated_image
from core.policy import is_manager_role
from core.security import decode_token
from database import get_db_connection

router = APIRouter(prefix="/api/v1/media", tags=["private-media"])
security = HTTPBearer()
PURPOSES = {"report_initial","report_proof","collection_proof","dispute_photo","support_attachment","message_attachment"}


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = decode_token(credentials.credentials)
    if not user:
        raise HTTPException(401, "Token invalide ou expiré")
    return user


def can_access_asset(cur, asset, user) -> bool:
    if is_manager_role(user.get("role", "")) or asset["uploader_id"] == user["user_id"]:
        return True
    resource_type, resource_id = asset["resource_type"], asset["resource_id"]
    if resource_type == "report":
        cur.execute("SELECT 1 FROM reports WHERE id=%s AND (user_id=%s OR agent_id=%s)", (resource_id,user["user_id"],user["user_id"]))
    elif resource_type == "collection":
        cur.execute("SELECT 1 FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE o.id=%s AND (s.user_id=%s OR o.collector_id=%s)", (resource_id,user["user_id"],user["user_id"]))
    elif resource_type == "conversation":
        cur.execute("SELECT 1 FROM conversation_participants WHERE conversation_id=%s AND user_id=%s", (resource_id,user["user_id"]))
    elif resource_type == "support":
        cur.execute("SELECT 1 FROM support_requests WHERE id=%s AND (author_id=%s OR assigned_to=%s)", (resource_id,user["user_id"],user["user_id"]))
    else:
        return False
    return bool(cur.fetchone())


def load_asset(cur, asset_id: str):
    try:
        UUID(asset_id)
    except ValueError:
        raise HTTPException(404, "Média introuvable") from None
    cur.execute("SELECT * FROM media_assets WHERE id=%s AND status<>'deleted' AND deleted_at IS NULL", (asset_id,))
    asset = cur.fetchone()
    if not asset:
        raise HTTPException(404, "Média introuvable")
    return asset


@router.post("")
async def upload_private_media(purpose: str = Form(...), file: UploadFile = File(...), user=Depends(current_user)):
    if purpose not in PURPOSES:
        raise HTTPException(422, "Usage de média invalide")
    content = await read_validated_image(file)
    conn = get_db_connection(); storage = get_media_storage(); stored = None
    try:
        asset_id, stored = store_media_with_compensation(conn,user["user_id"],purpose,content,file.content_type,storage=storage)
        conn.commit()
        return {"id":asset_id,"purpose":purpose,"mime_type":stored.mime_type,"size_bytes":stored.size_bytes,"width":stored.width,"height":stored.height,"sha256":stored.sha256,"status":"temporary"}
    except Exception:
        conn.rollback()
        if stored:
            storage.delete(stored.storage_key)
        raise
    finally:
        conn.close()


@router.get("/{asset_id}/metadata")
def media_metadata(asset_id: str, user=Depends(current_user)):
    conn=get_db_connection(); cur=conn.cursor(cursor_factory=RealDictCursor)
    asset=load_asset(cur,asset_id)
    if not can_access_asset(cur,asset,user): cur.close(); conn.close(); raise HTTPException(404,"Média introuvable")
    result={key:asset[key] for key in ("id","purpose","resource_type","resource_id","mime_type","size_bytes","width","height","sha256","status","created_at")}
    cur.close();conn.close();return result


@router.get("/{asset_id}")
def read_private_media(asset_id: str, user=Depends(current_user)):
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor);asset=load_asset(cur,asset_id)
    if not can_access_asset(cur,asset,user): cur.close();conn.close();raise HTTPException(404,"Média introuvable")
    storage=get_media_storage()
    if not storage.exists(asset["storage_key"]): cur.close();conn.close();raise HTTPException(404,"Média introuvable")
    with storage.open(asset["storage_key"]) as stream: content=stream.read()
    cur.close();conn.close()
    return Response(content,media_type=asset["mime_type"],headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff","Content-Disposition":f'inline; filename="media{asset["extension"]}"'})


@router.delete("/{asset_id}")
def delete_temporary_media(asset_id: str, user=Depends(current_user)):
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor);asset=load_asset(cur,asset_id)
    if asset["uploader_id"]!=user["user_id"] or asset["status"]!="temporary": cur.close();conn.close();raise HTTPException(404,"Média introuvable")
    cur.execute("UPDATE media_assets SET status='deleted',deleted_at=NOW() WHERE id=%s",(asset_id,));conn.commit();cur.close();conn.close();get_media_storage().delete(asset["storage_key"]);return {"deleted":True}


@router.get("/legacy/report/{report_id}/{kind}")
def read_legacy_report_media(report_id:int,kind:str,user=Depends(current_user)):
    if kind not in {"initial","proof"}: raise HTTPException(404,"Média introuvable")
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT user_id,agent_id,initial_media_asset_id,proof_media_asset_id,photo_base64,photo_preuve_base64 FROM reports WHERE id=%s",(report_id,));report=cur.fetchone()
    if not report or not (is_manager_role(user.get("role","")) or user["user_id"] in {report["user_id"],report["agent_id"]}): cur.close();conn.close();raise HTTPException(404,"Média introuvable")
    asset_id=report["initial_media_asset_id"] if kind=="initial" else report["proof_media_asset_id"]
    legacy=report["photo_base64"] if kind=="initial" else report["photo_preuve_base64"]
    cur.close();conn.close()
    if asset_id: return read_private_media(str(asset_id),user)
    if not legacy: raise HTTPException(404,"Média introuvable")
    try: content=base64.b64decode(legacy,validate=True)
    except ValueError: raise HTTPException(404,"Média introuvable") from None
    return Response(content,media_type="image/jpeg",headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})
