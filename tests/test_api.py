"""Hermetic API integration tests; never fall back to the personal database."""
import base64
import os
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

import auth
import main
from core.security import create_access_token, hash_password
from database import require_test_database_url


class TransactionConnection:
    def __init__(self, connection): self.connection = connection
    def cursor(self, *args, **kwargs): return self.connection.cursor(*args, **kwargs)
    def commit(self): pass
    def close(self): pass
    def __getattr__(self, name): return getattr(self.connection, name)


@pytest.fixture
def api(monkeypatch):
    try:
        url = require_test_database_url(os.getenv("TEST_DATABASE_URL"))
    except RuntimeError as error:
        pytest.skip(str(error))
    connection = psycopg2.connect(url)
    connection.autocommit = False
    wrapped = TransactionConnection(connection)
    monkeypatch.setattr(main, "get_db_connection", lambda: wrapped)
    monkeypatch.setattr(auth, "get_db_connection", lambda: wrapped)
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


def test_citizen_cannot_access_manager_reports(api):
    client, users = api
    assert client.get("/api/v1/signalements", headers=bearer(users["citoyen"])).status_code == 403
