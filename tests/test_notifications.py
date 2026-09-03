from app.services.notifications import create_notification
import pytest


class Cursor:
    def __init__(self):
        self.executed = None

    def execute(self, query, params):
        self.executed = (query, params)

    def fetchone(self):
        return (17,)

    def close(self):
        pass


class Connection:
    def __init__(self):
        self.cursor_instance = Cursor()

    def cursor(self):
        return self.cursor_instance


def test_notification_writer_uses_recipient_and_metadata():
    conn = Connection()
    assert create_notification(conn, 8, "report_received", "Reçu", "Signalement reçu", "/reports/4", "notification.report_received", {"report_id": 4}) == 17
    params = conn.cursor_instance.executed[1]
    assert params[:6] == (8, "report_received", "Reçu", "Signalement reçu", "/reports/4", "notification.report_received")
    assert params[6].adapted == {"report_id": 4}


def test_notification_writer_adapts_empty_and_legacy_metadata():
    conn = Connection()
    create_notification(conn, 8, "legacy", "Titre", "Contenu")
    params = conn.cursor_instance.executed[1]
    assert params[5] is None
    assert params[6].adapted == {}


def test_notification_writer_accepts_text_and_numbers():
    conn = Connection()
    create_notification(conn, 8, "assigned", "Titre", "Contenu", translation_params={"zone": "Akwa", "count": 2})
    assert conn.cursor_instance.executed[1][6].adapted == {"zone": "Akwa", "count": 2}


def test_notification_writer_rejects_non_json_values():
    with pytest.raises(ValueError):
        create_notification(Connection(), 8, "bad", "Titre", "Contenu", translation_params={"bad": object()})
