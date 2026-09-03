import jwt
import hashlib
import os
import secrets
import bcrypt
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Optional

APP_ENV = os.getenv("APP_ENV", "development").lower()
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    if APP_ENV in {"production", "staging"}:
        raise RuntimeError("JWT_SECRET_KEY est obligatoire hors développement")
    SECRET_KEY = "development-only-change-me-at-least-32-bytes"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if hashed_password.startswith("$2"):
            return bcrypt.checkpw(
                plain_password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        salt, hash_value = hashed_password.split("$")
        check_hash = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
        return secrets.compare_digest(check_hash, hash_value)
    except (ValueError, TypeError):
        return False

def create_access_token(user_id: int, role: str, expires_delta: Optional[timedelta] = None):
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    issued_at = datetime.utcnow()
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "access",
        "iat": issued_at,
        "jti": str(uuid4()),
        "exp": expire,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload if payload.get("type", "access") == "access" else None
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
