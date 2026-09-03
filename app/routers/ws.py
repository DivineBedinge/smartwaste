"""Disabled experimental WebSocket router; never register without JWT authentication."""

EXPERIMENTAL_DO_NOT_REGISTER = True

from fastapi import APIRouter, WebSocket
from ws_manager import manager

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.close(code=1008, reason="Route expérimentale désactivée")
