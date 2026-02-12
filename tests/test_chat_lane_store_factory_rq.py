from __future__ import annotations

from services.api.chat_lane_store import MemoryLaneStore
from services.api.chat_lane_store_factory import get_chat_lane_store, reset_chat_lane_stores


def test_factory_uses_redis_store_when_available(monkeypatch) -> None:
    reset_chat_lane_stores()

    class _Client:
        def __init__(self):
            self.ping_calls = 0

        def ping(self) -> None:
            self.ping_calls += 1

    client = _Client()

    class _FakeRedisLaneStore:
        def __init__(self, *, redis_client, tenant_id, claim_ttl_sec, debounce_ms):
            self.redis_client = redis_client
            self.tenant_id = tenant_id
            self.claim_ttl_sec = claim_ttl_sec
            self.debounce_ms = debounce_ms

    monkeypatch.setattr("services.api.redis_clients.get_redis_client", lambda url, decode_responses=True: client)
    monkeypatch.setattr("services.api.chat_redis_lane_store.RedisLaneStore", _FakeRedisLaneStore)

    store = get_chat_lane_store(
        tenant_id="tenant-a",
        is_pytest=False,
        redis_url="redis://x",
        debounce_ms=123,
        claim_ttl_sec=456,
    )

    assert isinstance(store, _FakeRedisLaneStore)
    assert store.redis_client is client
    assert store.tenant_id == "tenant-a"
    assert store.claim_ttl_sec == 456
    assert store.debounce_ms == 123
    assert client.ping_calls == 1


def test_factory_falls_back_to_memory_when_redis_unavailable(monkeypatch) -> None:
    reset_chat_lane_stores()

    class _BadClient:
        @staticmethod
        def ping() -> None:
            raise RuntimeError("redis down")

    monkeypatch.setattr("services.api.redis_clients.get_redis_client", lambda url, decode_responses=True: _BadClient())

    store = get_chat_lane_store(
        tenant_id="   ",
        is_pytest=False,
        redis_url="redis://x",
        debounce_ms=11,
        claim_ttl_sec=22,
    )

    assert isinstance(store, MemoryLaneStore)

    # tenant_id blank should normalize to default key and be cached.
    same = get_chat_lane_store(
        tenant_id="default",
        is_pytest=False,
        redis_url="redis://x",
        debounce_ms=11,
        claim_ttl_sec=22,
    )
    assert same is store
