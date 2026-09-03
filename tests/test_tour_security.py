import pytest
from fastapi import HTTPException

import main


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = None
    def execute(self, query, params):
        self.executed = (query, params)
    def fetchall(self):
        return self.rows
    def close(self):
        pass


class Connection:
    def __init__(self, rows):
        self.value = Cursor(rows)
    def cursor(self, **_kwargs):
        return self.value
    def close(self):
        pass


def test_itinerary_query_is_scoped_to_agent(monkeypatch):
    connection = Connection([{"id": 1, "lat": 4.0, "lon": 9.0}, {"id": 2, "lat": 4.1, "lon": 9.1}])
    monkeypatch.setattr(main, "get_db_connection", lambda: connection)
    monkeypatch.setattr(main, "get_route", lambda _points: {"geometry": {}, "distance_m": 10, "duration_s": 2})
    main.itineraire_tournee(4, {"user_id": 7, "role": "agent"})
    assert connection.value.executed[1] == (4, False, 7)
    assert "t.agent_id = %s" in connection.value.executed[0]


def test_empty_itinerary_is_not_disclosed(monkeypatch):
    monkeypatch.setattr(main, "get_db_connection", lambda: Connection([]))
    with pytest.raises(HTTPException) as error:
        main.itineraire_tournee(99, {"user_id": 7, "role": "agent"})
    assert error.value.status_code == 404
