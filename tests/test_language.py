import importlib

from core import config


def test_default_language_is_french(monkeypatch):
    monkeypatch.delenv("DEFAULT_LANGUAGE", raising=False)
    assert config.get_default_language() == "fr"


def test_default_language_accepts_english(monkeypatch):
    monkeypatch.setenv("DEFAULT_LANGUAGE", "en")
    assert config.get_default_language() == "en"


def test_invalid_default_language_falls_back_to_french(monkeypatch):
    monkeypatch.setenv("DEFAULT_LANGUAGE", "de")
    assert config.get_default_language() == "fr"


def test_registration_model_uses_configured_default(monkeypatch):
    monkeypatch.setenv("DEFAULT_LANGUAGE", "en")
    reloaded = importlib.reload(config)
    assert reloaded.DEFAULT_LANGUAGE == "en"
    monkeypatch.setenv("DEFAULT_LANGUAGE", "fr")
    importlib.reload(config)
