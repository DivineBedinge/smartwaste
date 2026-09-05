from __future__ import annotations

import json
import logging
import os
import time
from uuid import uuid4

from fastapi import Request
from starlette.responses import JSONResponse

from app.services.rate_limit import InMemoryRateLimiter, limit_for_path


logger = logging.getLogger("smartwaste.http")
limiter = InMemoryRateLimiter()


def _request_id(request: Request) -> str:
    incoming = request.headers.get("x-request-id", "")
    return incoming if 1 <= len(incoming) <= 80 and incoming.replace("-", "").isalnum() else str(uuid4())


def _log(event: dict) -> None:
    if os.getenv("LOG_FORMAT", "text").lower() == "json":
        logger.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
    else:
        logger.info("request id=%s method=%s route=%s status=%s duration_ms=%s", event["request_id"], event["method"], event["route"], event["status"], event["duration_ms"])


async def security_observability_middleware(request: Request, call_next):
    request_id = _request_id(request)
    started = time.perf_counter()
    query_keys = {key.lower() for key in request.query_params.keys()}
    if query_keys.intersection({"token", "access_token", "jwt"}):
        response = JSONResponse({"detail": "Requête non autorisée", "request_id": request_id}, status_code=400)
    else:
        limit = limit_for_path(request.url.path)
        authorization = request.headers.get("authorization", "")
        identity = authorization if authorization else (request.client.host if request.client else "unknown")
        key = limiter.opaque_key(f"{request.url.path}:{identity}")
        if limit and not limiter.allow(key, limit):
            response = JSONResponse({"detail": "Trop de requêtes", "request_id": request_id}, status_code=429, headers={"Retry-After": str(int(limit.window_seconds))})
        else:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("unhandled request_id=%s route=%s", request_id, request.url.path)
                response = JSONResponse({"detail": "Erreur interne", "request_id": request_id}, status_code=500)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(self), microphone=()"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = os.getenv("CONTENT_SECURITY_POLICY", "default-src 'self'; img-src 'self' data: https://*.tile.openstreetmap.org; style-src 'self' 'unsafe-inline' https://unpkg.com; script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store"
    if os.getenv("HTTPS_ENABLED", "false").lower() == "true":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    _log({"timestamp": time.time(), "service": "api", "environment": os.getenv("APP_ENV", "development"), "request_id": request_id, "method": request.method, "route": request.url.path, "status": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2)})
    return response
