import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
STATIC = ROOT / "static"
ROLE_PAGES = ("citoyen.html", "agent.html", "ramasseur.html", "gestionnaire.html")


def test_tailwind_is_local_and_reproducible():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["devDependencies"]["tailwindcss"] == "3.4.17"
    assert "--minify" in package["scripts"]["build:css"]
    assert (STATIC / "smartwaste.css").stat().st_size < 100_000
    for page in ROLE_PAGES:
        html = (STATIC / page).read_text(encoding="utf-8")
        assert "cdn.tailwindcss.com" not in html
        assert '/static/smartwaste.css' in html


def test_common_shell_covers_roles_and_accessibility():
    script = (STATIC / "ui-shell.js").read_text(encoding="utf-8")
    for role in ("citoyen", "agent", "ramasseur", "admin"):
        assert role in script
    for contract in ("aria-label", "aria-current", "aria-live", "aria-expanded", "textContent", "createElement"):
        assert contract in script
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert forbidden not in script


def test_ios_safe_area_dark_mode_and_reduced_motion():
    source = (STATIC / "src" / "smartwaste.css").read_text(encoding="utf-8")
    assert "safe-area-inset-bottom" in source
    assert "prefers-reduced-motion" in source
    assert "prefers-contrast" in source
    assert ".dark" in source
    for page in ROLE_PAGES:
        html = (STATIC / page).read_text(encoding="utf-8")
        assert "viewport-fit=cover" in html
        assert "apple-mobile-web-app-capable" in html
        assert "/static/ui-shell.js" in html


def test_mascot_and_assistant_are_local_and_controlled():
    mascot = (STATIC / "mascot-recycleur.svg").read_text(encoding="utf-8")
    script = (STATIC / "ui-shell.js").read_text(encoding="utf-8")
    assert "http://www.w3.org/2000/svg" in mascot
    assert "<script" not in mascot and "onload=" not in mascot
    assert "/api/v1/geo/assistant" in script
    assert "sessionStorage" in script
    assert "sw_assistant_side" in script
    assert "unread-count" in script


def test_manifest_and_service_worker_cache_pwa_assets():
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert any(icon["purpose"] == "maskable" for icon in manifest["icons"])
    worker = (STATIC / "sw.js").read_text(encoding="utf-8")
    for asset in ("ui-shell.js", "smartwaste.css", "mascot-recycleur.svg"):
        assert asset in worker
