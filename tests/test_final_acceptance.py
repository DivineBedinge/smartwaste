from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_final_evidence_documents_cover_roles_and_limits():
    trace = (ROOT / "docs/final/traceability.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "docs/final/acceptance.md").read_text(encoding="utf-8")
    for role in ("citoyen", "agent", "ramasseur", "gestionnaire"):
        assert role in trace.lower()
        assert role in acceptance.lower()
    assert "non execute" in (ROOT / "docs/final/scientific-evaluation.md").read_text(encoding="utf-8")


def test_readme_does_not_claim_unverified_classifier_score():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "97,35" not in readme
    assert "aucune performance" in readme.lower()


def test_demo_runbook_uses_scoped_project_and_no_real_secret():
    runbook = (ROOT / "docs/final/demo-runbook.md").read_text(encoding="utf-8")
    assert "-p smartwaste_demo" in runbook
    assert "<secret-aleatoire" in runbook
    assert "smartwaste_db" not in runbook
