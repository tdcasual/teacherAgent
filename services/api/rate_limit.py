"""In-memory sliding-window rate limiter middleware.

Environment variables:
    RATE_LIMIT_RPM – max requests per minute per client IP (default: 120, 0 = disabled)
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

_SKIP_PATHS = {"/health", "/health/"}

_rpm = int(os.getenv("RATE_LIMIT_RPM", "120") or "0")
_window_sec = 60.0
_buckets: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    if _rpm <= 0 or request.url.path in _SKIP_PATHS or os.getenv("PYTEST_CURRENT_TEST"):
        return await call_next(request)

    now = time.monotonic()
    key = _client_key(request)
    bucket = _buckets[key]

    # Evict entries outside the window
    cutoff = now - _window_sec
    while bucket and bucket[0] < cutoff:
        bucket.popleft()

    if len(bucket) >= _rpm:
        retry_after = int(bucket[0] + _window_sec - now) + 1
        return JSONResponse(
            status_code=429,
            content={"detail": "rate_limit_exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    bucket.append(now)
    return await call_next(request)
