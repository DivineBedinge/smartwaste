import time
from typing import Dict, Optional


class PositionRateLimiter:
    def __init__(self, interval_seconds: float = 10.0):
        self.interval_seconds = interval_seconds
        self._last_update: Dict[int, float] = {}

    def allow(self, actor_id: int, now: Optional[float] = None) -> bool:
        current = time.monotonic() if now is None else now
        previous = self._last_update.get(actor_id)
        if previous is not None and current - previous < self.interval_seconds:
            return False
        self._last_update[actor_id] = current
        return True


def position_is_fresh(age_seconds: float, max_age_seconds: float = 120.0) -> bool:
    return 0 <= age_seconds <= max_age_seconds