from app.services.notifications import create_notification


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
    assert create_notification(conn, 8, "report_received", "Reçu", "Signalement reçu", "/reports/4") == 17
    assert conn.cursor_instance.executed[1] == (8, "report_received", "Reçu", "Signalement reçu", "/reports/4")