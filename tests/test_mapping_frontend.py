from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_common_map_is_wired_to_all_roles_and_uses_safe_dom():
    source=(ROOT/'static'/'map-common.js').read_text(encoding='utf-8')
    assert 'innerHTML' not in source and 'insertAdjacentHTML' not in source and 'document.write' not in source
    assert 'textContent' in source and 'replaceChildren' in source and 'AbortController' in source
    for page in ('citoyen.html','agent.html','ramasseur.html','gestionnaire.html'):
        assert '/static/map-common.js' in (ROOT/'static'/page).read_text(encoding='utf-8')

def test_map_handles_offline_empty_error_and_destroy():
    source=(ROOT/'static'/'map-common.js').read_text(encoding='utf-8')
    for marker in ('map.offline','map.empty','map.error','provider?.destroy','removeEventListener'):
        assert marker in source
