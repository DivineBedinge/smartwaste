import asyncio

import pytest
from fastapi import HTTPException

import main


class Cursor:
    def execute(self, _query, _params):
        pass
    def fetchone(self):
        return None
    def close(self):
        pass


class Connection:
    def cursor(self):
        return Cursor()
    def close(self):
        pass


def test_agent_position_requires_active_mission(monkeypatch):
    monkeypatch.setattr(main.gps_rate_limiter, "allow", lambda _user_id: True)
    monkeypatch.setattr(main, "get_db_connection", Connection)
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.envoyer_position(4.05, 9.70, {"user_id": 8, "role": "agent"}))
    assert error.value.status_code == 409
