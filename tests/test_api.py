"""Hermetic API integration tests; never fall back to the personal database."""
import base64
import os
from datetime import date, timedelta
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

import auth
import main
from app.routers import communications, media, workflows
from app.services.automation import run_daily_automation
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


def test_report_assignment_private_proof_and_human_decision(api):
    client, users = api
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    report=client.post("/api/v1/signalements",files={"file":("r.png",image,"image/png")},data={"lat":"4.05","lon":"9.70","client_id":str(uuid4())},headers=bearer(users["citoyen"]));assert report.status_code==200 and report.json()["status"]=="valide"
    report_id=report.json()["id"]
    assigned=client.put(f"/api/v1/signalements/{report_id}/assigner?agent_id={users['agent']['id']}",headers=bearer(users["admin"]));assert assigned.status_code==200 and assigned.json()["status"]=="assigne"
    assert client.put(f"/api/v1/signalements/{report_id}/prendre-en-charge",headers=bearer(users["ramasseur"])).status_code==403
    assert client.put(f"/api/v1/signalements/{report_id}/prendre-en-charge",headers=bearer(users["agent"])).status_code==200
    proof=client.post(f"/api/v1/signalements/{report_id}/preuve-traitement",files={"file":("p.png",image,"image/png")},data={"lat":"4.05","lon":"9.70","comment":"Nettoyé"},headers=bearer(users["agent"]));assert proof.status_code==200 and proof.json()["status"]=="verification_requise"
    decision=client.patch(f"/api/v1/signalements/{report_id}/preuves/{proof.json()['proof_id']}/decision",json={"decision":"acceptee"},headers=bearer(users["admin"]));assert decision.status_code==200 and decision.json()["report_status"]=="cloture"
    dispute=client.post(f"/api/v1/signalements/{report_id}/contester",data={"reason":"incomplet","comment":"Le site reste sale"},headers=bearer(users["citoyen"]));assert dispute.status_code==200 and dispute.json()["report_status"]=="reouvert"


def test_domestic_collection_accept_prove_and_confirm(api):
    client,users=api
    plan=client.post("/api/v1/gestionnaire/plans",json={"name":"Hebdo test","frequency":"hebdomadaire","price":1000,"service_area":None},headers=bearer(users["admin"]));assert plan.status_code==200
    subscription=client.post("/api/v1/abonnements-domestiques",json={"plan_id":plan.json()[0],"lat":4.05,"lon":9.70},headers=bearer(users["citoyen"]));assert subscription.status_code==200
    start=date.today();generated=client.post("/api/v1/gestionnaire/collectes/generer",json={"start":start.isoformat(),"until":(start+timedelta(days=14)).isoformat()},headers=bearer(users["admin"]));assert generated.status_code==200 and generated.json()["created"]>=1
    rows=client.get("/api/v1/gestionnaire/collectes",headers=bearer(users["admin"])).json();occurrence_id=next(row[0] for row in rows if row[1]==subscription.json()["id"])
    assigned=client.post(f"/api/v1/gestionnaire/collectes/{occurrence_id}/affecter",json={"collector_id":users["ramasseur"]["id"]},headers=bearer(users["admin"]));assert assigned.status_code==200 and assigned.json()["status"]=="proposee"
    assert client.patch(f"/api/v1/ramasseur/collectes/{occurrence_id}/proposition",json={"accept":True},headers=bearer(users["ramasseur"])).json()["status"]=="acceptee"
    for status in ("en_route","arrivee"):
        assert client.patch(f"/api/v1/ramasseur/collectes/{occurrence_id}/status",json={"status":status},headers=bearer(users["ramasseur"])).status_code==200
    image=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    proof=client.post(f"/api/v1/ramasseur/collectes/{occurrence_id}/preuve",files={"file":("c.png",image,"image/png")},headers=bearer(users["ramasseur"]));assert proof.status_code==200 and proof.json()["status"]=="en_attente_confirmation"
    confirmed=client.patch(f"/api/v1/citoyen/collectes/{occurrence_id}/decision",json={"confirm":True},headers=bearer(users["citoyen"]));assert confirmed.status_code==200 and confirmed.json()["status"]=="confirmee"


def test_collection_refusal_requires_reason_and_releases_assignment(api):
    client, users = api
    plan = client.post("/api/v1/gestionnaire/plans", json={"name":"Refus test","frequency":"hebdomadaire","price":500}, headers=bearer(users["admin"])).json()
    subscription = client.post("/api/v1/abonnements-domestiques", json={"plan_id":plan[0],"lat":4.05,"lon":9.70}, headers=bearer(users["citoyen"])).json()
    start = date.today()
    client.post("/api/v1/gestionnaire/collectes/generer", json={"start":start.isoformat(),"until":(start+timedelta(days=7)).isoformat()}, headers=bearer(users["admin"]))
    occurrence_id = next(row[0] for row in client.get("/api/v1/gestionnaire/collectes",headers=bearer(users["admin"])).json() if row[1]==subscription["id"])
    client.post(f"/api/v1/gestionnaire/collectes/{occurrence_id}/affecter",json={"collector_id":users["ramasseur"]["id"]},headers=bearer(users["admin"]))
    assert client.patch(f"/api/v1/ramasseur/collectes/{occurrence_id}/proposition",json={"accept":False},headers=bearer(users["ramasseur"])).status_code == 422
    refused = client.patch(f"/api/v1/ramasseur/collectes/{occurrence_id}/proposition",json={"accept":False,"reason":"Véhicule indisponible"},headers=bearer(users["ramasseur"]))
    assert refused.status_code == 200 and refused.json()["status"] == "refusee"
    assert all(row[0] != occurrence_id for row in client.get("/api/v1/ramasseur/collectes",headers=bearer(users["ramasseur"])).json())


def test_daily_automation_is_idempotent(api):
    _, _users = api
    result = run_daily_automation(main.get_db_connection(), date.today())
    duplicate = run_daily_automation(main.get_db_connection(), date.today())
    assert result["status"] == "completed"
    assert duplicate["status"] == "already_completed"
