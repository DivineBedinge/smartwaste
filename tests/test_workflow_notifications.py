from datetime import date

from app.routers import workflows


class Cursor:
    def __init__(self, results):
        self.results = iter(results)
        self.current = None
    def execute(self, _query, _params=None):
        self.current = next(self.results, None)
    def fetchone(self):
        return self.current
    def close(self):
        pass


class Connection:
    def __init__(self, results):
        self.value = Cursor(results)
    def cursor(self):
        return self.value
    def commit(self):
        pass
    def close(self):
        pass


def test_assignment_notifies_selected_collector(monkeypatch):
    connection = Connection([(date(2026, 9, 7), "Akwa", "programmee"), (8, "Akwa", 4, [0]), (0,), (21, 8, "affectee")])
    sent = []
    monkeypatch.setattr(workflows, "get_db_connection", lambda: connection)
    monkeypatch.setattr(workflows, "notify_collection", lambda *args, **kwargs: sent.append((args, kwargs)))
    result = workflows.assign_collection(21, workflows.CollectorAssignment(collector_id=8), {"user_id": 1, "role": "gestionnaire"})
    assert result == {"id": 21, "collector_id": 8, "status": "affectee"}
    assert sent[0][0][1:5] == (8, 21, "collection_assigned", "Nouvelle collecte affectée")


def test_missed_collection_notifies_its_collector(monkeypatch):
    connection = Connection([("arrivee",), (21, "manquee")])
    sent = []
    monkeypatch.setattr(workflows, "get_db_connection", lambda: connection)
    monkeypatch.setattr(workflows, "notify_collection", lambda *args, **kwargs: sent.append((args, kwargs)))
    result = workflows.update_collector_collection(21, workflows.CollectionStatusUpdate(status="manquee", missed_reason="absent"), {"user_id": 8, "role": "ramasseur"})
    assert result == {"id": 21, "status": "manquee"}
    assert sent[0][0][1:4] == (8, 21, "collection_missed")
    assert sent[0][1]["reason"] == "absent"
