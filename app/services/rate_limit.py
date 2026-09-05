from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimit:
    maximum: int
    window_seconds: float


class InMemoryRateLimiter:
    """Mono-instance limiter with bounded, non-sensitive hashed keys."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def opaque_key(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:24]

    def allow(self, key: str, limit: RateLimit) -> bool:
        now = self.clock()
        boundary = now - limit.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= boundary:
                events.popleft()
            if len(events) >= limit.maximum:
                return False
            events.append(now)
            if not events:
                self._events.pop(key, None)
            return True


SENSITIVE_LIMITS = (
    ("/api/v1/auth/login", RateLimit(30, 60)),
    ("/api/v1/media", RateLimit(120, 60)),
    ("/api/v1/geo/assistant", RateLimit(30, 60)),
    ("/api/v1/geo/tours", RateLimit(120, 60)),
    ("/api/v1/conversations", RateLimit(60, 60)),
    ("/api/v1/messages", RateLimit(60, 60)),
    ("/api/v1/signalements", RateLimit(30, 60)),
    ("/api/v1/chatbot", RateLimit(30, 60)),
    ("/api/v1/callback-requests", RateLimit(20, 60)),
    ("/api/v1/demandes-support", RateLimit(20, 60)),
    ("/api/v1/gestionnaire", RateLimit(120, 60)),
    ("/api/v1/agent/position", RateLimit(30, 60)),
)


def limit_for_path(path: str) -> RateLimit | None:
    return next((limit for prefix, limit in SENSITIVE_LIMITS if path.startswith(prefix)), None)
