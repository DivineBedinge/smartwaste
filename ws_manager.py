import json
from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "citoyen": [],
            "agent": [],
            "gestionnaire": []
        }

    async def connect(self, websocket: WebSocket, role: str):
        await websocket.accept()
        self.active_connections.setdefault(role, []).append(websocket)

    def disconnect(self, websocket: WebSocket, role: str):
        if role in self.active_connections:
            self.active_connections[role].remove(websocket)

    async def broadcast_to_role(self, role: str, message: dict):
        for connection in self.active_connections[role]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                self.disconnect(connection, role)

    async def broadcast_to_all(self, message: dict):
        for role in ["citoyen", "agent", "gestionnaire"]:
            await self.broadcast_to_role(role, message)

manager = ConnectionManager()