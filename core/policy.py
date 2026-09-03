from enum import Enum


class Role(str, Enum):
    GESTIONNAIRE = "gestionnaire"
    AGENT = "agent"
    RAMASSEUR = "ramasseur"
    CITOYEN = "citoyen"


LEGACY_MANAGER_ROLES = {"admin", "municipal", Role.GESTIONNAIRE.value}
PROFESSIONAL_ROLES = {
    Role.AGENT.value,
    Role.RAMASSEUR.value,
    *LEGACY_MANAGER_ROLES,
}


PUBLIC_REPORT_STATES = {
    "soumis",
    "en_analyse",
    "a_verifier",
    "en_attente_validation",
    "classifie",
    "valide",
    "rejete",
    "hors_sujet",
    "assigne",
    "en_route",
    "en_cours",
    "traite",
    "verification_requise",
    "cloture",
    "reouvert",
}

REPORT_TRANSITIONS = {
    "soumis": {"en_analyse", "a_verifier", "classifie", "en_attente_validation", "rejete", "hors_sujet"},
    "en_analyse": {"a_verifier", "classifie", "rejete", "hors_sujet"},
    "a_verifier": {"classifie", "en_attente_validation", "valide", "rejete", "hors_sujet"},
    "en_attente_validation": {"classifie", "valide", "rejete", "hors_sujet"},
    "classifie": {"valide", "rejete", "hors_sujet"},
    "valide": {"assigne", "en_cours", "rejete"},
    "assigne": {"en_route", "en_cours", "reouvert"},
    "en_route": {"en_cours", "reouvert"},
    "en_cours": {"traite", "verification_requise", "reouvert"},
    "traite": {"verification_requise", "cloture", "reouvert"},
    "verification_requise": {"cloture", "reouvert", "en_cours"},
    "cloture": {"reouvert"},
    "reouvert": {"en_analyse", "a_verifier", "valide", "assigne"},
    "rejete": {"reouvert"},
    "hors_sujet": {"reouvert"},
}


DOMESTIC_COLLECTION_STATES = {
    "programmee",
    "affectee",
    "en_route",
    "arrivee",
    "effectuee",
    "confirmee",
    "manquee",
    "reprogrammee",
}

COLLECTION_TRANSITIONS = {
    "programmee": {"affectee", "reprogrammee", "manquee"},
    "affectee": {"en_route", "reprogrammee", "manquee"},
    "en_route": {"arrivee", "manquee"},
    "arrivee": {"effectuee", "manquee"},
    "effectuee": {"confirmee"},
    "confirmee": set(),
    "manquee": {"reprogrammee"},
    "reprogrammee": {"affectee", "manquee"},
}


def is_manager_role(role: str) -> bool:
    return role in LEGACY_MANAGER_ROLES


def can_transition(transitions: dict[str, set[str]], current: str, target: str) -> bool:
    return target in transitions.get(current, set())