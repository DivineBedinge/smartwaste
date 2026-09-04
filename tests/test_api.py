"""Hermetic API integration tests; never fall back to the personal database."""
import base64
import os
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

import auth
import main
from app.routers import communications, media, workflows
from core.security import create_access_token, hash_password
from database import require_test_database_url


class TransactionConnection:
    def __init__(self, connection): self.connection = connection
    def cursor(self, *args, **kwargs): return self.connection.cursor(*args, **kwargs)
    def commit(self): pass
    def close(self): pass
    def __getattr__(self, name): return getattr(self.connection, name)


@pytest.fixture
def api(monkeypatch, tmp_path):
    try:
        url = require_test_database_url(os.getenv("TEST_DATABASE_URL"))
    except RuntimeError as error:
        pytest.skip(str(error))
    connection = psycopg2.connect(url)
    monkeypatch.setenv("MEDIA_STORAGE_PATH", str(tmp_path / "private-media"))
    connection.autocommit = False
    wrapped = TransactionConnection(connection)
    monkeypatch.setattr(main, "get_db_connection", lambda: wrapped)
    monkeypatch.setattr(auth, "get_db_connection", lambda: wrapped)
    monkeypatch.setattr(communications, "get_db_connection", lambda: wrapped)
    monkeypatch.setattr(media, "get_db_connection", lambda: wrapped)
    monkeypatch.setattr(workflows, "get_db_connection", lambda: wrapped)
    monkeypatch.setattr(main, "predict_severity", lambda _: ("faible", 0.99))
    monkeypatch.setattr(main, "predict_type", lambda _: ("plastic", 0.98))
    users = {}
    with connection.cursor() as cursor:
        for role in ("admin", "agent", "ramasseur", "citoyen"):
            email = f"{role}-{uuid4()}@example.test"
            cursor.execute(
                "INSERT INTO users(email,password_hash,role,arrondissement) VALUES (%s,%s,%s,%s) RETURNING id",
                (email, hash_password("test-password"), role, "Douala V"),
            )
            user_id = cursor.fetchone()[0]
            users[role] = {"id": user_id, "email": email, "token": create_access_token(user_id, role)}
    try:
        yield TestClient(main.app), users
    finally:
        connection.rollback()
        connection.close()


def bearer(user): return {"Authorization": f"Bearer {user['token']}"}


def test_health_without_external_service():
    assert TestClient(main.app).get("/").status_code == 200


def test_login_for_each_role(api):
    client, users = api
    for user in users.values():
        response = client.post("/api/v1/auth/login", json={"email": user["email"], "password": "test-password"})
        assert response.status_code == 200
        assert response.json()["access_token"]


def test_registration_cannot_choose_privileged_role(api):
    client, _ = api
    response = client.post("/api/v1/auth/register", json={"email": f"new-{uuid4()}@example.test", "password": "test-password", "role": "admin"})
    assert response.status_code == 200
    assert response.json()["role"] == "citoyen"


def test_create_report_is_idempotent_without_ai_or_network(api):
    client, users = api
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    client_id = str(uuid4())
    request = {"files": {"file": ("test.png", image, "image/png")}, "data": {"lat": "4.0511", "lon": "9.7069", "client_id": client_id}, "headers": bearer(users["citoyen"])}
    first = client.post("/api/v1/signalements", **request)
    second = client.post("/api/v1/signalements", **request)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["duplicate"] is True
    media = client.get(f"/api/v1/media/legacy/report/{first.json()['id']}/initial", headers=bearer(users["citoyen"]))
    assert media.status_code == 200
    assert media.headers["cache-control"] == "private, no-store"


def test_citizen_cannot_access_manager_reports(api):
    client, users = api
    assert client.get("/api/v1/signalements", headers=bearer(users["citoyen"])).status_code == 403


def test_contextual_communication_is_idempotent_private_and_closable(api):
    client, users = api
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    report = client.post(
        "/api/v1/signalements",
        files={"file": ("test.png", image, "image/png")},
        data={"lat": "4.0511", "lon": "9.7069", "client_id": str(uuid4())},
        headers=bearer(users["citoyen"]),
    )
    assert report.status_code == 200
    conversation = client.post(
        "/api/v1/conversations",
        json={"resource_type": "report", "resource_id": report.json()["id"]},
        headers=bearer(users["citoyen"]),
    )
    assert conversation.status_code == 200
    conversation_id = conversation.json()["id"]
    client_id = str(uuid4())
    first = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        data={"client_id": client_id, "body": "Bonjour <script>alert(1)</script>"},
        files={"file": ("proof.png", image, "image/png")},
        headers=bearer(users["citoyen"]),
    )
    duplicate = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        data={"client_id": client_id, "body": "Bonjour <script>alert(1)</script>"},
        headers=bearer(users["citoyen"]),
    )
    assert first.status_code == duplicate.status_code == 200
    assert first.json()["id"] == duplicate.json()["id"]
    attachment = client.get(f"/api/v1/messages/{first.json()['id']}/attachment", headers=bearer(users["citoyen"]))
    assert attachment.status_code == 200 and attachment.headers["content-type"] == "image/png"
    assert client.get(f"/api/v1/messages/{first.json()['id']}/attachment", headers=bearer(users["ramasseur"])).status_code == 404
    listed = client.get("/api/v1/conversations", headers=bearer(users["admin"]))
    assert listed.status_code == 200
    assert any(row["id"] == conversation_id for row in listed.json())
    assert client.get("/api/v1/conversations", headers=bearer(users["ramasseur"])).json() == []
    assert client.patch(f"/api/v1/conversations/{conversation_id}/close", headers=bearer(users["admin"])).status_code == 200
    closed = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        data={"client_id": str(uuid4()), "body": "Après clôture"},
        headers=bearer(users["citoyen"]),
    )
    assert closed.status_code == 409


def test_support_and_callback_are_available_to_citizen(api):
    client, users = api
    support = client.post(
        "/api/v1/demandes-support",
        json={"category": "suggestion", "subject": "Amélioration", "description": "Ajouter un bac", "resource_type": "general"},
        headers=bearer(users["citoyen"]),
    )
    assert support.status_code == 200
    callback = client.post(
        "/api/v1/callback-requests",
        json={"reason": "Besoin d'aide"},
        headers=bearer(users["citoyen"]),
    )
    assert callback.status_code == 200
    manager_notifications = client.get("/api/v1/notifications?limit=10&unread=true", headers=bearer(users["admin"]))
    assert manager_notifications.status_code == 200
    assert {row["notification_type"] for row in manager_notifications.json()} >= {"support_received", "callback_requested"}
