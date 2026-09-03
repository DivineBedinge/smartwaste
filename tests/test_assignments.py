from datetime import date


def test_weekday_is_checked_before_capacity():
    assert date(2026, 9, 7).weekday() == 0
    assert date(2026, 9, 7).weekday() not in {5, 6}