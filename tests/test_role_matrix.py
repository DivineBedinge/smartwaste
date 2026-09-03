import pytest

from core.policy import is_agent_role, is_collector_role, is_manager_role


@pytest.mark.parametrize("role", ["gestionnaire", "admin", "municipal"])
def test_manager_roles_include_canonical_and_legacy_aliases(role):
    assert is_manager_role(role)


@pytest.mark.parametrize("role", ["citoyen", "agent", "ramasseur", "unknown"])
def test_non_managers_are_rejected(role):
    assert not is_manager_role(role)


def test_agent_and_collector_are_strictly_distinct():
    assert is_agent_role("agent")
    assert not is_agent_role("ramasseur")
    assert is_collector_role("ramasseur")
    assert not is_collector_role("agent")
