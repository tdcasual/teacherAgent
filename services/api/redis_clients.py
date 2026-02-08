from __future__ import annotations

import os
from typing import Dict, Tuple

import redis

_REDIS_CLIENTS: Dict[Tuple[str, bool], redis.Redis] = {}


def get_redis_client(url: str | None = None, *, decode_responses: bool = True) -> redis.Redis:
    redis_url = str(url or os.getenv("REDIS_URL", "redis://localhost:6379/0") or "redis://localhost:6379/0")
    key = (redis_url, bool(decode_responses))
    client = _REDIS_CLIENTS.get(key)
    if client is None:
        client = redis.Redis.from_url(redis_url, decode_responses=decode_responses)
        _REDIS_CLIENTS[key] = client
    return client
