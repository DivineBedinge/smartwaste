from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


PRODUCTION_ENVS = {"production", "demo", "staging"}
WEAK_SECRETS = {"", "replace-with-a-random-secret", "development-only-change-me-at-least-32-bytes", "secret", "changeme"}


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    cors_origins: tuple[str, ...]
    websocket_origins: tuple[str, ...]
    https_enabled: bool
    chatbot_enabled: bool
    log_format: str


def _csv(name: str, fallback: str = "") -> tuple[str, ...]:
    return tuple(value.strip().rstrip("/") for value in os.getenv(name, fallback).split(",") if value.strip())


def load_runtime_config() -> RuntimeConfig:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    origins = _csv("CORS_ORIGINS", "http://localhost:8000")
    websocket_origins = _csv("WEBSOCKET_ORIGINS", ",".join(origins))
    config = RuntimeConfig(
        environment=environment,
        cors_origins=origins,
        websocket_origins=websocket_origins,
        https_enabled=os.getenv("HTTPS_ENABLED", "false").lower() == "true",
        chatbot_enabled=os.getenv("CHATBOT_ENABLED", "true").lower() == "true",
        log_format=os.getenv("LOG_FORMAT", "text").lower(),
    )
    validate_runtime_config(config)
    return config


def validate_runtime_config(config: RuntimeConfig) -> None:
    if config.environment not in {"development", "test", "demo", "staging", "production"}:
        raise RuntimeError("APP_ENV invalide")
    if not config.cors_origins or any(origin == "*" for origin in config.cors_origins):
        raise RuntimeError("CORS_ORIGINS doit être une liste explicite")
    if config.log_format not in {"text", "json"}:
        raise RuntimeError("LOG_FORMAT invalide")
    if config.environment not in PRODUCTION_ENVS:
        return
    secret = os.getenv("JWT_SECRET_KEY", "")
    if secret in WEAK_SECRETS or len(secret) < 32:
        raise RuntimeError("Configuration JWT insuffisante pour cet environnement")
    database_url = os.getenv("DATABASE_URL", "")
    parsed = urlparse(database_url)
    if not parsed.scheme.startswith("postgres") or not parsed.password or parsed.password.lower() in {"password", "changeme", "test-only-password"}:
        raise RuntimeError("Configuration PostgreSQL insuffisante pour cet environnement")
    media = Path(os.getenv("MEDIA_STORAGE_PATH", "")).expanduser()
    if not media.is_absolute() or str(media).lower().startswith(("/tmp", "c:\\windows\\temp")):
        raise RuntimeError("MEDIA_STORAGE_PATH doit être absolu et persistant")
    if not config.https_enabled:
        raise RuntimeError("HTTPS_ENABLED doit être actif")
    if any(not origin.startswith("https://") for origin in config.cors_origins + config.websocket_origins):
        raise RuntimeError("Les origines doivent utiliser HTTPS")
