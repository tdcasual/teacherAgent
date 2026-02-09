from __future__ import annotations

from typing import Dict

from .chat_lane_store import ChatLaneStore, MemoryLaneStore


_CHAT_LANE_STORES: Dict[str, ChatLaneStore] = {}


def get_chat_lane_store(
    *,
    tenant_id: str,
    is_pytest: bool,
    redis_url: str,
    debounce_ms: int,
    claim_ttl_sec: int,
) -> ChatLaneStore:
    tenant_key = str(tenant_id or "default").strip() or "default"
    store = _CHAT_LANE_STORES.get(tenant_key)
    if store is None:
        if is_pytest:
            store = MemoryLaneStore(
                debounce_ms=debounce_ms,
                claim_ttl_sec=claim_ttl_sec,
            )
        else:
            from .chat_redis_lane_store import RedisLaneStore
            from .redis_clients import get_redis_client

            store = RedisLaneStore(
                redis_client=get_redis_client(redis_url, decode_responses=True),
                tenant_id=tenant_key,
                claim_ttl_sec=claim_ttl_sec,
                debounce_ms=debounce_ms,
            )
        _CHAT_LANE_STORES[tenant_key] = store
    return store


def reset_chat_lane_stores() -> None:
    _CHAT_LANE_STORES.clear()
