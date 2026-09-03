import os


SUPPORTED_LANGUAGES = {"fr", "en"}


def get_default_language() -> str:
    language = os.getenv("DEFAULT_LANGUAGE", "fr").strip().lower()
    return language if language in SUPPORTED_LANGUAGES else "fr"


DEFAULT_LANGUAGE = get_default_language()
