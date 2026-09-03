from core.classification import AUTO_ACCEPT_THRESHOLD, decide_severity


def test_threshold_equal_is_automatically_accepted():
    decision = decide_severity("critique", AUTO_ACCEPT_THRESHOLD)
    assert decision.status == "valide"
    assert not decision.human_review_required


def test_threshold_above_is_automatically_accepted():
    decision = decide_severity("faible", 0.91)
    assert decision.status == "valide"
    assert not decision.human_review_required


def test_threshold_below_requires_human_review():
    decision = decide_severity("moderee", 0.79)
    assert decision.status == "en_attente_validation"
    assert decision.human_review_required


def test_out_of_scope_always_requires_human_review():
    decision = decide_severity("hors_sujet", 0.99)
    assert decision.status == "en_attente_validation"
    assert decision.out_of_scope


def test_model_failure_keeps_report_analyzable():
    decision = decide_severity(None, None, model_error=True)
    assert decision.status == "en_analyse"
    assert decision.human_review_required