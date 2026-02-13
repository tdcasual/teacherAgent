"""In-memory sliding-window rate limiter middleware.

Environment variables:
    RATE_LIMIT_RPM – max requests per minute per client IP (default: 120, 0 = disabled)
    RATE_LIMIT_MAX_BUCKETS – max distinct client buckets retained in memory (default: 4096)
    RATE_LIMIT_TRUST_X_FORWARDED_FOR – whether to trust X-Forwarded-For (default: false)
    RATE_LIMIT_TRUSTED_PROXY_IPS – comma-separated proxy IP allowlist when trusting XFF
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
_bucket_last_seen: dict[str, float] = {}
_max_buckets = max(1, int(os.getenv("RATE_LIMIT_MAX_BUCKETS", "4096") or "4096"))
_trust_x_forwarded_for = str(os.getenv("RATE_LIMIT_TRUST_X_FORWARDED_FOR", "") or "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_trusted_proxy_ips = {
    item.strip()
    for item in str(os.getenv("RATE_LIMIT_TRUSTED_PROXY_IPS", "") or "").split(",")
    if item.strip()
}


def _should_trust_forwarded_for(request: Request) -> bool:
    if not _trust_x_forwarded_for:
        return False
    if not _trusted_proxy_ips:
        return True
    client = request.client
    host = client.host if client else ""
    return host in _trusted_proxy_ips


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and _should_trust_forwarded_for(request):
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


def _drop_bucket(key: str) -> None:
    _buckets.pop(key, None)
    _bucket_last_seen.pop(key, None)


def _sweep_stale_buckets(now: float) -> None:
    cutoff = now - _window_sec
    stale_keys = []
    for key, bucket in _buckets.items():
        if not bucket:
            stale_keys.append(key)
            continue
        # If the newest timestamp is outside the window, the whole bucket is stale.
        if bucket[-1] < cutoff:
            stale_keys.append(key)
    for key in stale_keys:
        _drop_bucket(key)


def _enforce_bucket_cap() -> None:
    if len(_buckets) <= _max_buckets:
        return
    overflow = len(_buckets) - _max_buckets
    oldest = sorted(_bucket_last_seen.items(), key=lambda item: item[1])[:overflow]
    for key, _seen in oldest:
        _drop_bucket(key)


async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    if _rpm <= 0 or request.url.path in _SKIP_PATHS or os.getenv("PYTEST_CURRENT_TEST"):
        return await call_next(request)

    now = time.monotonic()
    _sweep_stale_buckets(now)
    _enforce_bucket_cap()
    key = _client_key(request)
    bucket = _buckets[key]

    # Evict entries outside the window
    cutoff = now - _window_sec
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if not bucket:
        _drop_bucket(key)
        bucket = _buckets[key]

    if len(bucket) >= _rpm:
        _bucket_last_seen[key] = now
        retry_after = int(bucket[0] + _window_sec - now) + 1
        return JSONResponse(
            status_code=429,
            content={"detail": "rate_limit_exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    bucket.append(now)
    _bucket_last_seen[key] = now
    _enforce_bucket_cap()
    return await call_next(request)
