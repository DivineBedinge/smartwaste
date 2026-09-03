from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ws_manager import manager
from database import get_db_connection
from app.services.live_tracking import get_all_agent_positions
from core.security import decode_token
from core.policy import is_manager_role

router = APIRouter(prefix="/api/v1/gestionnaire", tags=["gestionnaire"])
security = HTTPBearer()

def check_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload or not is_manager_role(payload.get("role", "")):
        raise HTTPException(403, "Accès refusé")
    return payload

@router.get("/agents-positions")
async def get_agents_positions(user: dict = Depends(check_admin)):
    """Récupère toutes les positions des agents en temps réel."""
    return await get_all_agent_positions()

@router.post("/broadcast")
async def broadcast_message(
    message: dict,
    user: dict = Depends(check_admin)
):
    """Le gestionnaire envoie un message à tous les agents/citoyens."""
    await manager.broadcast_to_all(message)
    return {"status": "broadcast"}
