from core.policy import (
    COLLECTION_TRANSITIONS,
    REPORT_TRANSITIONS,
    Role,
    can_transition,
    is_manager_role,
    validate_transition,
)


def test_four_roles_are_explicit():
    assert {role.value for role in Role} == {
        "gestionnaire",
        "agent",
        "ramasseur",
        "citoyen",
    }


def test_legacy_manager_roles_remain_compatible():
    assert is_manager_role("admin")
    assert is_manager_role("municipal")
    assert is_manager_role("gestionnaire")
    assert not is_manager_role("agent")


def test_report_transitions_require_assignment_before_route():
    assert can_transition(REPORT_TRANSITIONS, "valide", "assigne")
    assert not can_transition(REPORT_TRANSITIONS, "valide", "en_route")
    assert not can_transition(REPORT_TRANSITIONS, "cloture", "traite")


def test_collection_transitions_require_assignment_and_arrival():
    assert can_transition(COLLECTION_TRANSITIONS, "programmee", "affectee")
    assert not can_transition(COLLECTION_TRANSITIONS, "programmee", "effectuee")
    assert can_transition(COLLECTION_TRANSITIONS, "manquee", "reprogrammee")
    assert can_transition(COLLECTION_TRANSITIONS, "proposee", "acceptee")
    assert not can_transition(COLLECTION_TRANSITIONS, "proposee", "en_route")


def test_transition_role_rules_are_enforced():
    from core.policy import REPORT_TRANSITION_ROLES
    validate_transition(REPORT_TRANSITIONS,"valide","assigne","gestionnaire",REPORT_TRANSITION_ROLES)
    import pytest
    with pytest.raises(PermissionError):
        validate_transition(REPORT_TRANSITIONS,"valide","assigne","agent",REPORT_TRANSITION_ROLES)
