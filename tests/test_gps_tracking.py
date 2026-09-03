from app.services.gps_tracking import PositionRateLimiter, position_is_fresh


def test_position_updates_are_rate_limited():
    limiter = PositionRateLimiter(10)
    assert limiter.allow(4, 100)
    assert not limiter.allow(4, 105)
    assert limiter.allow(4, 110)


def test_position_freshness_has_upper_bound():
    assert position_is_fresh(120)
    assert not position_is_fresh(121)
    assert not position_is_fresh(-1)