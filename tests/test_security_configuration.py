from datetime import timedelta

import jwt

from core import security


def test_access_token_is_short_lived_and_typed():
    token = security.create_access_token(12, "citoyen", timedelta(minutes=2))
    payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
    assert payload["type"] == "access"
    assert payload["user_id"] == 12
    assert payload["exp"] - payload["iat"] <= 120
    assert payload["jti"]


def test_refresh_token_cannot_be_used_as_access_token():
    token = jwt.encode({"user_id": 12, "role": "citoyen", "type": "refresh"}, security.SECRET_KEY, algorithm=security.ALGORITHM)
    assert security.decode_token(token) is None
