from enum import Enum


class Role(str, Enum):
    GESTIONNAIRE = "gestionnaire"
    AGENT = "agent"
    RAMASSEUR = "ramasseur"
    CITOYEN = "citoyen"


MANAGER_ROLES = {Role.GESTIONNAIRE.value, "admin", "municipal"}
LEGACY_MANAGER_ROLES = MANAGER_ROLES
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
    "proposee",
    "affectee",
    "acceptee",
    "refusee",
    "en_route",
    "arrivee",
    "effectuee",
    "en_attente_confirmation",
    "confirmee",
    "contestee",
    "manquee",
    "reprogrammee",
    "annulee",
}

COLLECTION_TRANSITIONS = {
    "programmee": {"proposee", "affectee", "reprogrammee", "manquee", "annulee"},
    "proposee": {"acceptee", "refusee", "reprogrammee", "annulee"},
    "affectee": {"acceptee", "en_route", "refusee", "reprogrammee", "manquee", "annulee"},
    "acceptee": {"en_route", "reprogrammee", "manquee", "annulee"},
    "refusee": {"programmee", "reprogrammee"},
    "en_route": {"arrivee", "manquee"},
    "arrivee": {"effectuee", "manquee"},
    "effectuee": {"en_attente_confirmation"},
    "en_attente_confirmation": {"confirmee", "contestee"},
    "contestee": {"confirmee", "reprogrammee"},
    "confirmee": set(),
    "manquee": {"reprogrammee"},
    "reprogrammee": {"proposee", "affectee", "manquee", "annulee"},
    "annulee": set(),
}


REPORT_TRANSITION_ROLES = {
    "valide": MANAGER_ROLES,
    "rejete": MANAGER_ROLES,
    "hors_sujet": MANAGER_ROLES,
    "assigne": MANAGER_ROLES,
    "en_route": {Role.AGENT.value},
    "en_cours": {Role.AGENT.value, *MANAGER_ROLES},
    "traite": {Role.AGENT.value, *MANAGER_ROLES},
    "verification_requise": {Role.AGENT.value, *MANAGER_ROLES},
    "cloture": MANAGER_ROLES,
    "reouvert": MANAGER_ROLES,
}


def validate_transition(transitions, current: str, target: str, role: str, role_rules=None) -> None:
    if not can_transition(transitions, current, target):
        raise ValueError("Transition invalide")
    if role_rules and target in role_rules and role not in role_rules[target]:
        raise PermissionError("Rôle non autorisé pour cette transition")


def is_manager_role(role: str) -> bool:
    return role in MANAGER_ROLES


def is_agent_role(role: str, *, include_managers: bool = False) -> bool:
    return role == Role.AGENT.value or (include_managers and is_manager_role(role))


def is_collector_role(role: str) -> bool:
    return role == Role.RAMASSEUR.value


def can_transition(transitions: dict[str, set[str]], current: str, target: str) -> bool:
    return target in transitions.get(current, set())
