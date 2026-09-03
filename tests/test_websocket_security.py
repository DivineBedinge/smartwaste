import asyncio

import main
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.security import create_access_token


class Socket:
    def __init__(self):
        self.messages = []
    async def accept(self):
        pass
    async def send_text(self, message):
        self.messages.append(message)


def test_websocket_messages_are_scoped_by_recipient():
    manager = main.WSManager()
    first, second = Socket(), Socket()
    asyncio.run(manager.connect(first, {"user_id": 1, "role": "citoyen"}))
    asyncio.run(manager.connect(second, {"user_id": 2, "role": "citoyen"}))
    asyncio.run(manager.send_to_user(1, {"type": "private"}))
    assert len(first.messages) == 1
    assert second.messages == []


def test_manager_channel_excludes_non_managers():
    manager = main.WSManager()
    citizen, manager_socket = Socket(), Socket()
    asyncio.run(manager.connect(citizen, {"user_id": 1, "role": "citoyen"}))
    asyncio.run(manager.connect(manager_socket, {"user_id": 2, "role": "gestionnaire"}))
    asyncio.run(manager.send_to_managers({"type": "management"}))
    assert citizen.messages == []
    assert len(manager_socket.messages) == 1


@pytest.mark.parametrize("subprotocols", [None, ["bearer", "invalid"]])
def test_websocket_rejects_missing_or_invalid_token(subprotocols):
    client = TestClient(main.app)
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/ws", subprotocols=subprotocols):
            pass
    assert error.value.code == 1008


def test_websocket_accepts_authenticated_citizen():
    client = TestClient(main.app)
    token = create_access_token(12, "citoyen")
    with client.websocket_connect("/ws", subprotocols=["bearer", token]) as websocket:
        websocket.send_text("ping")
