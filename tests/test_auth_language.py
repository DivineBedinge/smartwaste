from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import auth


class Cursor:
    def __init__(self, result):
        self.result = result
        self.executed = None
    def execute(self, query, params):
        self.executed = (query, params)
    def fetchone(self):
        return self.result
    def close(self):
        pass


class Connection:
    def __init__(self, result):
        self.value = Cursor(result)
    def cursor(self):
        return self.value
    def commit(self):
        pass
    def close(self):
        pass


def credentials():
    return SimpleNamespace(credentials="token")


def test_language_can_be_changed_to_english(monkeypatch):
    connection = Connection(("en",))
    monkeypatch.setattr(auth, "decode_token", lambda _: {"user_id": 7})
    monkeypatch.setattr(auth, "get_db_connection", lambda: connection)
    assert auth.update_language(auth.LanguageUpdate(language_preference="en"), credentials()) == {"language_preference": "en"}
    assert connection.value.executed[1] == ("en", 7)


def test_invalid_language_is_rejected():
    with pytest.raises(HTTPException) as error:
        auth.update_language(auth.LanguageUpdate(language_preference="de"), credentials())
    assert error.value.status_code == 422


def test_invalid_token_is_rejected(monkeypatch):
    monkeypatch.setattr(auth, "decode_token", lambda _: None)
    with pytest.raises(HTTPException) as error:
        auth.update_language(auth.LanguageUpdate(language_preference="fr"), credentials())
    assert error.value.status_code == 401


def test_missing_user_is_rejected(monkeypatch):
    monkeypatch.setattr(auth, "decode_token", lambda _: {"user_id": 404})
    monkeypatch.setattr(auth, "get_db_connection", lambda: Connection(None))
    with pytest.raises(HTTPException) as error:
        auth.update_language(auth.LanguageUpdate(language_preference="fr"), credentials())
    assert error.value.status_code == 404
