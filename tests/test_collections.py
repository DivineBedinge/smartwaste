from datetime import date, datetime

from app.services.collections import generate_occurrence_dates, missing_occurrences


def test_weekly_and_biweekly_generation():
    start = date(2026, 9, 7)
    assert len(generate_occurrence_dates("hebdomadaire", start, date(2026, 9, 30), {0})) == 4
    assert len(generate_occurrence_dates("bimensuelle", start, date(2026, 10, 31), {0})) == 4


def test_monthly_generation_handles_short_months():
    dates = generate_occurrence_dates("mensuelle", date(2026, 1, 31), date(2026, 4, 30), set(range(7)))
    assert dates == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 28), date(2026, 4, 28)]


def test_generation_is_idempotent():
    candidate = datetime(2026, 9, 7, 9)
    assert missing_occurrences(4, [candidate], set()) == [candidate]
    assert missing_occurrences(4, [candidate], {(4, candidate)}) == []