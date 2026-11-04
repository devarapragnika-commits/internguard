"""In-memory rate limit for analyze routes. No extra service is required."""

from __future__ import annotations

import threading
import time

from backend.config import get_analyze_rate_limit, get_analyze_rate_window

_MESSAGE = "Too many analysis requests. Wait a minute and try again."


class RateLimiter:
    def __init__(self, limit: int = 30, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        stamp = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.setdefault(key, [])
            cutoff = stamp - self.window
            hits[:] = [item for item in hits if item > cutoff]
            if len(hits) >= self.limit:
                return False
            hits.append(stamp)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_limiter = RateLimiter()
_configured = False
_config_lock = threading.Lock()


def configure_limiter() -> RateLimiter:
    global _configured
    with _config_lock:
        if not _configured:
            _limiter.limit = get_analyze_rate_limit()
            _limiter.window = get_analyze_rate_window()
            _configured = True
        return _limiter


def reset_limiter() -> None:
    global _configured
    with _config_lock:
        _limiter.reset()
        _configured = False
        _limiter.limit = get_analyze_rate_limit()
        _limiter.window = get_analyze_rate_window()


def allow_analyze(client: str) -> bool:
    return configure_limiter().allow(client)


def rate_limit_message() -> str:
    return _MESSAGE
