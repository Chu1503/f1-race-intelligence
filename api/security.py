from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Header, HTTPException, Request, status

from config import settings


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)


_limiter = SlidingWindowRateLimiter()


def rate_limit(name: str, *, limit: int, window_seconds: int = 60) -> Callable:
    def dependency(request: Request) -> None:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        client = forwarded or (request.client.host if request.client else "unknown")
        _limiter.check(f"{name}:{client}", limit, window_seconds)
    return dependency


def require_service_key(x_api_key: str | None = Header(default=None)) -> None:
    configured = settings.SERVICE_API_KEY
    if not configured:
        if settings.ENVIRONMENT.lower() == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Protected endpoints are disabled until SERVICE_API_KEY is configured.",
            )
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid service credential.",
        )
