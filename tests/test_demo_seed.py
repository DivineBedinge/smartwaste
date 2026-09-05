import pytest

from scripts.seed_demo import require_safe_target, required_passwords


def test_demo_seed_refuses_unknown_and_personal_databases():
    for url in (
        "postgresql://u:p@localhost/app",
        "postgresql://u:p@localhost/smartwaste_db",
    ):
        with pytest.raises(RuntimeError):
            require_safe_target(url)


def test_demo_seed_accepts_only_demo_or_test():
    assert require_safe_target("postgresql://u:p@localhost/smartwaste_test") == "smartwaste_test"
    assert require_safe_target("postgresql://u:p@postgres/smartwaste_demo") == "smartwaste_demo"


def test_demo_passwords_are_never_defaults(monkeypatch):
    for role in ("CITOYEN", "AGENT", "RAMASSEUR", "GESTIONNAIRE"):
        monkeypatch.delenv(f"DEMO_{role}_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="obligatoires"):
        required_passwords()
