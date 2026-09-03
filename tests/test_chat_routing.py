from app.router import chatbot_cache_key, simple_chat_response
import main


def test_french_greeting_is_deterministic_and_does_not_mention_metal():
    result = simple_chat_response("hey ça va ?")
    assert result["intention"] == "greeting"
    assert "métal" not in result["reponse"].lower()


def test_english_greeting_is_short_and_english():
    result = simple_chat_response("hello")
    assert result["langue"] == "en"
    assert result["reponse"].startswith("Hello")


def test_out_of_scope_question_has_controlled_fallback():
    result = simple_chat_response("Quel est le score du football ?")
    assert result["intention"] == "out_of_scope"


def test_waste_question_continues_to_knowledge_pipeline():
    assert simple_chat_response("Comment trier une bouteille en plastique ?") is None


def test_cache_is_partitioned_by_language_intent_and_version():
    fr = chatbot_cache_key("fr", "waste_information", "pile")
    en = chatbot_cache_key("en", "waste_information", "pile")
    greeting = chatbot_cache_key("fr", "greeting", "pile")
    assert len({fr, en, greeting}) == 3


def test_greeting_bypasses_redis_database_and_models(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("external service must not be called")
    monkeypatch.setattr(main, "obtenir_reponse_cachee", forbidden)
    monkeypatch.setattr(main, "get_db_connection", forbidden)
    monkeypatch.setattr(main, "predict_type", forbidden)
    result = main._process_chatbot_ask("hey ça va ?", session_id="session-with-metal")
    assert result["intention"] == "greeting"
    assert "métal" not in result["reponse"].lower()


def test_ai_disabled_returns_controlled_fallback(monkeypatch):
    monkeypatch.setattr(main, "heavy_ai_disabled", lambda: True)
    result = main._process_chatbot_ask("Comment trier une bouteille ?")
    assert result["source"] == "degraded"
    assert "indisponible" in result["reponse"]
