from core.policy import COLLECTION_TRANSITIONS, REPORT_TRANSITIONS, can_transition


def test_closed_report_requires_reopen_before_editing():
    assert can_transition(REPORT_TRANSITIONS, "cloture", "reouvert")
    assert not can_transition(REPORT_TRANSITIONS, "cloture", "traite")


def test_missed_collection_requires_rescheduling():
    assert can_transition(COLLECTION_TRANSITIONS, "arrivee", "manquee")
    assert can_transition(COLLECTION_TRANSITIONS, "manquee", "reprogrammee")
    assert not can_transition(COLLECTION_TRANSITIONS, "manquee", "confirmee")


def test_rejected_report_cannot_reenter_normal_processing():
    assert not can_transition(REPORT_TRANSITIONS, "rejete", "valide")
    assert can_transition(REPORT_TRANSITIONS, "rejete", "reouvert")