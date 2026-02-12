from __future__ import annotations

import logging
import threading
from typing import Dict

from .chat_lane_store import ChatLaneStore, MemoryLaneStore

_log = logging.getLogger(__name__)

_CHAT_LANE_STORES: Dict[str, ChatLaneStore] = {}
_STORE_LOCK = threading.Lock()


def get_chat_lane_store(
    *,
    tenant_id: str,
    is_pytest: bool,
    redis_url: str,
    debounce_ms: int,
    claim_ttl_sec: int,
) -> ChatLaneStore:
    tenant_key = str(tenant_id or "default").strip() or "default"
    with _STORE_LOCK:
        store = _CHAT_LANE_STORES.get(tenant_key)
        if store is None:
            if is_pytest:
                store = MemoryLaneStore(
                    debounce_ms=debounce_ms,
                    claim_ttl_sec=claim_ttl_sec,
                )
            else:
                try:
                    from .chat_redis_lane_store import RedisLaneStore
                    from .redis_clients import get_redis_client

                    client = get_redis_client(redis_url, decode_responses=True)
                    client.ping()
                    store = RedisLaneStore(
                        redis_client=client,
                        tenant_id=tenant_key,
                        claim_ttl_sec=claim_ttl_sec,
                        debounce_ms=debounce_ms,
                    )
                except Exception:
                    _log.warning(
                        "Redis unavailable for chat lane store; using in-memory fallback"
                    )
                    store = MemoryLaneStore(
                        debounce_ms=debounce_ms,
                        claim_ttl_sec=claim_ttl_sec,
                    )
            _CHAT_LANE_STORES[tenant_key] = store
    return store


def reset_chat_lane_stores() -> None:
    with _STORE_LOCK:
        _CHAT_LANE_STORES.clear()
