from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
from app.services.rate_limit import InMemoryRateLimiter, RateLimit
from core.runtime_config import RuntimeConfig, validate_runtime_config


def test_production_rejects_weak_configuration(monkeypatch, tmp_path):
    config = RuntimeConfig("production", ("https://demo.invalid",), ("https://demo.invalid",), True, True, "json")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:password@db/app")
    monkeypatch.setenv("MEDIA_STORAGE_PATH", str(tmp_path.resolve()))
    with pytest.raises(RuntimeError, match="JWT"):
        validate_runtime_config(config)


def test_rate_limiter_is_deterministic_and_uses_opaque_keys():
    now = [10.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    key = limiter.opaque_key("Bearer sensitive-token")
    assert "sensitive-token" not in key
    assert limiter.allow(key, RateLimit(2, 10))
    assert limiter.allow(key, RateLimit(2, 10))
    assert not limiter.allow(key, RateLimit(2, 10))
    now[0] = 21
    assert limiter.allow(key, RateLimit(2, 10))


def test_security_headers_request_id_and_token_query_rejection():
    client = TestClient(main.app)
    response = client.get("/health/live", headers={"X-Request-ID": "test-request-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    refused = client.get("/health/live?token=never-allowed")
    assert refused.status_code == 400
    assert "never-allowed" not in refused.text


def test_websocket_rejects_untrusted_origin():
    client = TestClient(main.app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws", headers={"Origin": "https://evil.invalid"}, subprotocols=["bearer", "invalid"]):
            pass


def test_generated_pwa_icons_have_exact_dimensions():
    static = Path(__file__).parents[1] / "static"
    expected = {"apple-touch-icon.png": (180, 180), "icon-192.png": (192, 192), "icon-512.png": (512, 512), "icon-maskable-512.png": (512, 512)}
    for filename, dimensions in expected.items():
        with Image.open(static / filename) as image:
            assert image.format == "PNG"
            assert image.size == dimensions


def test_logout_purges_private_browser_state():
    script = (Path(__file__).parents[1] / "static" / "ui-shell.js").read_text(encoding="utf-8")
    for contract in ("clearPrivateState", "sw_assistant_history", "SmartWasteGeoCache", "PURGE_PRIVATE"):
        assert contract in script


def test_demo_docker_runs_as_non_root_and_separates_automation():
    root = Path(__file__).parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    compose = (root / "docker-compose.demo.yml").read_text(encoding="utf-8")
    assert "USER smartwaste" in dockerfile
    assert "npm run build:css" in dockerfile
    assert "automation:" in compose and "run_automation.py" in compose
    assert "smartwaste_db" not in compose
