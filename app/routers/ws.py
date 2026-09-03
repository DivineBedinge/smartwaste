from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ws_manager import manager

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Le rôle peut être passé en query param : ?role=citoyen
    role = websocket.query_params.get("role", "citoyen")
    await manager.connect(websocket, role)
    try:
        while True:
            # On reçoit les messages (pour l'instant on peut les ignorer ou les traiter)
            data = await websocket.receive_text()
            # Broadcast éventuel
            await manager.broadcast_to_all({"type": "ping", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket, role)