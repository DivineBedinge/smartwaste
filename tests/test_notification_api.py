from app.routers import workflows


class Cursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = None
        self.rowcount = 0

    def execute(self, query, params=None):
        self.executed = (query, params)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        pass


class Connection:
    def __init__(self, cursor):
        self.value = cursor
    def cursor(self, **_kwargs):
        return self.value
    def commit(self):
        pass
    def close(self):
        pass


def test_notification_list_contract_and_recipient_filter(monkeypatch):
    row = {"id": 4, "translation_key": "notification.collection_assigned", "translation_params": {"collection_id": 9}}
    cursor = Cursor([row])
    monkeypatch.setattr(workflows, "get_db_connection", lambda: Connection(cursor))
    assert workflows.list_notifications({"user_id": 12}) == [row]
    query, params = cursor.executed
    assert "translation_key" in query and "translation_params" in query
    assert params == (12, None, None, 20, 0)


def test_individual_read_is_scoped_to_recipient(monkeypatch):
    cursor = Cursor([(5, True)])
    monkeypatch.setattr(workflows, "get_db_connection", lambda: Connection(cursor))
    assert workflows.mark_notification_read(5, {"user_id": 12}) == {"id": 5, "is_read": True}
    assert cursor.executed[1] == (5, 12)


def test_read_all_is_scoped_to_recipient(monkeypatch):
    cursor = Cursor(); cursor.rowcount = 3
    monkeypatch.setattr(workflows, "get_db_connection", lambda: Connection(cursor))
    assert workflows.mark_all_notifications_read({"user_id": 12}) == {"updated": 3}
    assert cursor.executed[1] == (12,)
