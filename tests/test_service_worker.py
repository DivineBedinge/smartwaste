from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "static" / "sw.js").read_text(encoding="utf-8")


def test_service_worker_excludes_private_api_responses():
    assert "url.pathname.startsWith('/api/')" in SOURCE
    assert "request.method !== 'GET'" in SOURCE


def test_service_worker_cleans_previous_smartwaste_caches():
    assert "caches.keys()" in SOURCE
    assert "key.startsWith(CACHE_PREFIX)" in SOURCE
    assert "caches.delete(key)" in SOURCE
