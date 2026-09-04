from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routers import communications, workflows
from app.services.notifications import validate_notification_link


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows


def test_notification_links_accept_only_internal_paths():
    assert validate_notification_link("/citoyen#support-3") == "/citoyen#support-3"
    with pytest.raises(ValueError):
        validate_notification_link("javascript:alert(1)")
    with pytest.raises(ValueError):
        validate_notification_link("https://evil.example/path")


def test_collection_conversation_requires_active_occurrence():
    cursor = Cursor([(5, 7), (10,)])
    users = communications.eligible_users(cursor, "collection", 2)
    assert users == {5, 7, 10}
    assert "o.status IN ('acceptee','en_route','arrivee','en_attente_confirmation')" in cursor.queries[0][0]


def test_unknown_conversation_resource_is_rejected():
    with pytest.raises(HTTPException) as error:
        communications.eligible_users(Cursor(), "user", 1)
    assert error.value.status_code == 422


def test_non_participant_cannot_open_conversation():
    cursor = Cursor([("open", "report", 4), None])
    with pytest.raises(HTTPException) as error:
        communications.require_participant(cursor, 9, 2)
    assert error.value.status_code == 404


def test_support_general_resource_cannot_have_identifier():
    with pytest.raises(HTTPException) as error:
        workflows.validate_support_resource(Cursor(), "general", 4, {"user_id": 2, "role": "citoyen"})
    assert error.value.status_code == 422


def test_support_resource_must_belong_to_requester():
    with pytest.raises(HTTPException) as error:
        workflows.validate_support_resource(Cursor([None]), "report", 4, {"user_id": 2, "role": "citoyen"})
    assert error.value.status_code == 403


def test_callback_context_requires_complete_pair():
    payload = communications.CallbackCreate(resource_type="report", reason="Rappelez-moi")
    with pytest.raises(HTTPException) as error:
        communications.request_callback(payload, {"user_id": 2, "role": "citoyen"})
    assert error.value.status_code == 422


def test_support_phone_rejects_unsafe_configuration(monkeypatch):
    monkeypatch.setenv("SUPPORT_PHONE", "javascript:alert(1)")
    with pytest.raises(HTTPException) as error:
        communications.support_phone({"user_id": 2, "role": "citoyen"})
    assert error.value.status_code == 503


def test_frontend_uses_safe_dom_and_persistent_outbox():
    source = Path("static/communications.js").read_text(encoding="utf-8")
    assert "innerHTML" not in source
    assert "textContent" in source
    assert "indexedDB.open" in source
    assert "crypto.randomUUID()" in source
    assert "auth_required" in source
    assert "javascript:" not in source


@pytest.mark.parametrize("page", ["citoyen.html", "agent.html", "ramasseur.html", "gestionnaire.html"])
def test_notification_center_is_loaded_for_every_role(page):
    source = Path("static", page).read_text(encoding="utf-8")
    assert "communications.js" in source
