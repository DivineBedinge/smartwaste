from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_collector_language_select_survives_translation():
    html = (ROOT / "static" / "ramasseur.html").read_text(encoding="utf-8")
    assert 'data-i18n="common.language"' in html
    assert 'id="language" data-language-select' in html
    assert '<label for="language" data-i18n="common.language">Langue</label>' in html
    assert '<script src="/static/i18n.js" defer></script>' in html


def test_collector_does_not_render_server_data_with_inner_html():
    html = (ROOT / "static" / "ramasseur.html").read_text(encoding="utf-8")
    assert "innerHTML" not in html
    assert "textContent" in html


def test_catalog_has_french_fallback_and_notification_parameters():
    source = (ROOT / "static" / "i18n.js").read_text(encoding="utf-8")
    assert "translations.fr[key]" in source
    assert "notification.collection_assigned" in source
    assert "{collection_id}" in source
    assert "localStorage.setItem('language_preference',lang)" in source
