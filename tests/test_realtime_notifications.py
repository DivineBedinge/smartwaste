import asyncio
from datetime import datetime, timezone
from pathlib import Path

import main


class Connection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def event():
    return {
        "notification_id": 41,
        "recipient_id": 7,
        "type": "new_message",
        "translation_key": "notification.new_message",
        "translation_params": {"conversation_id": 3},
        "resource_type": "conversation",
        "resource_id": 3,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


def test_dispatch_targets_only_recipient_after_database_visibility(monkeypatch):
    connection = Connection()
    sent, acknowledged = [], []
    monkeypatch.setattr(main, "pending_notification_events", lambda conn: [event()])
    monkeypatch.setattr(main, "acknowledge_notification_event", lambda conn, notification_id: acknowledged.append(notification_id))

    async def send_to_user(user_id, payload):
        sent.append((user_id, payload))

    monkeypatch.setattr(main.ws_manager, "send_to_user", send_to_user)
    asyncio.run(main.dispatch_notification_outbox_once(connection))
    assert sent[0][0] == 7
    assert sent[0][1] == {
        "event": "notification", "notification_id": 41, "type": "new_message",
        "translation_key": "notification.new_message",
        "translation_params": {"conversation_id": 3}, "resource_type": "conversation",
        "resource_id": 3, "created_at": "2026-01-01T00:00:00+00:00",
    }
    assert acknowledged == [41]
    assert connection.commits == 1


def test_failed_delivery_is_not_acknowledged_and_remains_retryable(monkeypatch):
    connection = Connection()
    failed, acknowledged = [], []
    monkeypatch.setattr(main, "pending_notification_events", lambda conn: [event()])
    monkeypatch.setattr(main, "acknowledge_notification_event", lambda *args: acknowledged.append(args))
    monkeypatch.setattr(main, "record_notification_failure", lambda conn, notification_id, error: failed.append((notification_id, error)))

    async def fail(*_):
        raise RuntimeError("offline")

    monkeypatch.setattr(main.ws_manager, "send_to_user", fail)
    asyncio.run(main.dispatch_notification_outbox_once(connection))
    assert acknowledged == []
    assert failed == [(41, "offline")]


def test_common_client_has_reconnect_polling_and_deduplication():
    source = Path("static/communications.js").read_text(encoding="utf-8")
    assert "Math.min(30000" in source
    assert "realtimeIds.has" in source
    assert "socket?.readyState!==WebSocket.OPEN" in source
    assert "['bearer',token()]" in source
    assert "innerHTML" not in source


def test_contextual_view_exposes_required_safe_states():
    source = Path("static/communications.js").read_text(encoding="utf-8")
    for value in ("pending", "sending", "failed", "auth_required", "participant_roles", "has_attachment"):
        assert value in source
    for page in ("citoyen.html", "agent.html", "ramasseur.html", "gestionnaire.html"):
        assert "communications.js" in Path("static", page).read_text(encoding="utf-8")
