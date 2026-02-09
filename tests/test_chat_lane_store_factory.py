from services.api.chat_lane_store import MemoryLaneStore
from services.api.chat_lane_store_factory import get_chat_lane_store, reset_chat_lane_stores


def test_chat_lane_store_factory_caches_per_tenant():
    store_1 = get_chat_lane_store(
        tenant_id="t1",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=10,
        claim_ttl_sec=5,
    )
    store_2 = get_chat_lane_store(
        tenant_id="t1",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=10,
        claim_ttl_sec=5,
    )
    store_3 = get_chat_lane_store(
        tenant_id="t2",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=10,
        claim_ttl_sec=5,
    )

    assert store_1 is store_2
    assert store_1 is not store_3
    assert isinstance(store_1, MemoryLaneStore)


def test_chat_lane_store_factory_reset():
    store_1 = get_chat_lane_store(
        tenant_id="t1",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=0,
        claim_ttl_sec=1,
    )

    reset_chat_lane_stores()

    store_2 = get_chat_lane_store(
        tenant_id="t1",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=0,
        claim_ttl_sec=1,
    )

    assert store_1 is not store_2
