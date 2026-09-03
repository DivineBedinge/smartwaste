# router.py
import re
from typing import Optional

CHAT_STRATEGY_VERSION = "v2"
GREETING_WORDS = {"bonjour", "salut", "hey", "hello", "hi", "bonsoir", "coucou", "how are you"}
OUT_OF_SCOPE_WORDS = {"football", "politique", "météo", "meteo", "religion", "casino"}


def normalize_chat_question(question: str) -> str:
    return re.sub(r"\s+", " ", (question or "").strip().lower())


def _contains_phrase(text: str, phrases: set[str]) -> bool:
    return any(re.search(rf"\b{re.escape(phrase)}\b", text) for phrase in phrases)


def detect_simple_intent(question: str) -> str:
    normalized = normalize_chat_question(question)
    if not normalized:
        return "invalid"
    if _contains_phrase(normalized, GREETING_WORDS):
        return "greeting"
    if _contains_phrase(normalized, OUT_OF_SCOPE_WORDS):
        return "out_of_scope"
    return "waste_information"


def simple_chat_response(question: str) -> Optional[dict]:
    normalized = normalize_chat_question(question)
    intent = detect_simple_intent(normalized)
    language = "en" if _contains_phrase(normalized, {"hello", "hi", "how are you"}) else "fr"
    if intent == "invalid":
        return {"langue": language, "source": "validation", "intention": intent, "reponse": "Please enter a question." if language == "en" else "Veuillez saisir une question."}
    if intent == "greeting":
        return {"langue": language, "source": "conversation", "intention": intent, "reponse": "Hello! How can I help you with waste sorting?" if language == "en" else "Bonjour ! Comment puis-je vous aider avec le tri des déchets ?"}
    if intent == "out_of_scope":
        return {"langue": language, "source": "controlled_fallback", "intention": intent, "reponse": "I can only help with waste management and recycling." if language == "en" else "Je peux uniquement vous aider sur les déchets et le recyclage."}
    return None


def chatbot_cache_key(language: str, intent: str, normalized_question: str) -> str:
    return f"{CHAT_STRATEGY_VERSION}:{language}:{intent}:{normalize_chat_question(normalized_question)}"

def is_faq_question(question: str) -> bool:
    """
    Détecte si la question est une FAQ (simple, courte, avec mots-clés génériques).
    """
    faq_keywords = ['acteurs', 'prix', 'réglementation', 'loi', 'recyclage', 'douala', 'coût', 'tarif']
    tokens = question.lower().split()
    if len(tokens) < 12:  # Questions courtes
        for kw in faq_keywords:
            if kw in question.lower():
                return True
    return False
