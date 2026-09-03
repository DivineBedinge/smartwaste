from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = (
    "<img src=x onerror=alert(1)>",
    "<script>alert(1)</script>",
    "\" onmouseover=\"alert(1)",
    "javascript:alert(1)",
)


def test_payloads_are_rendered_as_text_by_safe_notification_paths():
    citizen = (ROOT / "static" / "citoyen.html").read_text(encoding="utf-8")
    assert "label.textContent = String(message)" in citizen
    assert "toast.innerHTML" not in citizen
    assert "item.innerHTML = `<span class=\"block\">${message}" not in citizen
    assert all(payload not in citizen for payload in PAYLOADS)


def test_agent_server_rows_and_leaflet_popups_use_dom_nodes():
    agent = (ROOT / "static" / "agent.html").read_text(encoding="utf-8")
    assert "marker.bindPopup(popup)" in agent
    assert "row.textContent" in agent
    assert "div.innerHTML = html" not in agent


def test_manager_toast_uses_text_content():
    manager = (ROOT / "static" / "gestionnaire.html").read_text(encoding="utf-8")
    assert "label.textContent = String(message)" in manager
    assert "toast.innerHTML" not in manager


def test_dynamic_html_sinks_are_tagged_and_urls_are_validated():
    security = (ROOT / "static" / "dom-security.js").read_text(encoding="utf-8")
    combined = "\n".join((ROOT / "static" / name).read_text(encoding="utf-8") for name in (
        "citoyen.html", "gestionnaire.html", "dashboard.html", "agent.html",
        "agent_map.html", "gestionnaire_map.html",
    ))
    assert "javascript:" not in combined.lower()
    assert "safeImageDataUrl" in combined
    assert "replaceAll('<', '&lt;')" in security
    assert "allowed.has(url.protocol)" in security
    assert not re.search(r"innerHTML\s*=\s*`[^`]*\$\{", combined, re.DOTALL)
    assert not re.search(r"bindPopup\s*\(\s*`[^`]*\$\{", combined, re.DOTALL)
