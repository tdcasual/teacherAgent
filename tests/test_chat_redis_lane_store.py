"""Tests for ChatRedisLaneStore — all Redis calls are mocked."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import services.api.chat_redis_lane_store as mod


# ── helpers ──────────────────────────────────────────────────────────────

def _make_store(tenant_id="t1", claim_ttl_sec=60, debounce_ms=500):
    fake_redis = MagicMock()
    fake_redis.register_script = MagicMock(return_value=MagicMock())
    store = mod.ChatRedisLaneStore(
        fake_redis,
        tenant_id=tenant_id,
        claim_ttl_sec=claim_ttl_sec,
        debounce_ms=debounce_ms,
    )
    return store, fake_redis


# ── 1. __init__ ──────────────────────────────────────────────────────────

class TestInit:
    def test_prefix_format(self):
        store, _ = _make_store(tenant_id="acme")
        assert store.prefix == "chat:acme"

    def test_tenant_id_none_defaults(self):
        store, _ = _make_store(tenant_id=None)
        assert store.prefix == "chat:default"

    def test_tenant_id_empty_defaults(self):
        store, _ = _make_store(tenant_id="")
        assert store.prefix == "chat:default"

    def test_tenant_id_whitespace_defaults(self):
        store, _ = _make_store(tenant_id="   ")
        assert store.prefix == "chat:default"

    def test_claim_ttl_clamped_negative(self):
        store, _ = _make_store(claim_ttl_sec=-10)
        assert store.claim_ttl_sec == 0

    def test_claim_ttl_none_becomes_zero(self):
        store, _ = _make_store(claim_ttl_sec=None)
        assert store.claim_ttl_sec == 0

    def test_debounce_ms_clamped_negative(self):
        store, _ = _make_store(debounce_ms=-1)
        assert store.debounce_ms == 0

    def test_debounce_ms_none_becomes_zero(self):
        store, _ = _make_store(debounce_ms=None)
        assert store.debounce_ms == 0

    def test_scripts_registered(self):
        _, fake_redis = _make_store()
        assert fake_redis.register_script.call_count == 2


# ── 2. Key generation ───────────────────────────────────────────────────

class TestKeys:
    def test_queue_key(self):
        store, _ = _make_store(tenant_id="t1")
        assert store._queue_key("L1") == "chat:t1:lane:L1:queue"

    def test_active_key(self):
        store, _ = _make_store(tenant_id="t1")
        assert store._active_key("L1") == "chat:t1:lane:L1:active"

    def test_recent_key(self):
        store, _ = _make_store(tenant_id="t1")
        assert store._recent_key("L1") == "chat:t1:lane:L1:recent"

    def test_queued_key(self):
        store, _ = _make_store(tenant_id="t1")
        assert store._queued_key() == "chat:t1:queued"


# ── 3. lane_load ─────────────────────────────────────────────────────────

class TestLaneLoad:
    def test_returns_dict(self):
        store, r = _make_store()
        r.llen.return_value = 3
        r.exists.return_value = 1
        result = store.lane_load("L1")
        assert result == {"queued": 3, "active": 1, "total": 4}

    def test_no_active(self):
        store, r = _make_store()
        r.llen.return_value = 0
        r.exists.return_value = 0
        result = store.lane_load("L1")
        assert result == {"queued": 0, "active": 0, "total": 0}


# ── 4. find_position ────────────────────────────────────────────────────

class TestFindPosition:
    def test_found(self):
        store, r = _make_store()
        r.lpos.return_value = 2
        assert store.find_position("L1", "j1") == 3

    def test_not_found(self):
        store, r = _make_store()
        r.lpos.return_value = None
        assert store.find_position("L1", "j1") == 0

    def test_exception_returns_zero(self):
        store, r = _make_store()
        r.lpos.side_effect = Exception("boom")
        assert store.find_position("L1", "j1") == 0


# ── 5. enqueue ──────────────────────────────────────────────────────────

class TestEnqueue:
    def test_dispatch_true(self):
        store, _ = _make_store()
        store._enqueue_script.return_value = [0, 0, 1, 1]
        info, dispatch = store.enqueue("j1", "L1")
        assert dispatch is True
        assert info["lane_queue_position"] == 0
        assert info["lane_active"] is True

    def test_dispatch_false(self):
        store, _ = _make_store()
        store._enqueue_script.return_value = [2, 3, 1, 0]
        info, dispatch = store.enqueue("j1", "L1")
        assert dispatch is False
        assert info["lane_queue_position"] == 2
        assert info["lane_queue_size"] == 3


# ── 6. finish ────────────────────────────────────────────────────────────

class TestFinish:
    def test_returns_next_job(self):
        store, _ = _make_store()
        store._finish_script.return_value = "j2"
        assert store.finish("j1", "L1") == "j2"

    def test_empty_string_returns_none(self):
        store, _ = _make_store()
        store._finish_script.return_value = ""
        assert store.finish("j1", "L1") is None

    def test_none_returns_none(self):
        store, _ = _make_store()
        store._finish_script.return_value = None
        assert store.finish("j1", "L1") is None


# ── 7. register_recent ──────────────────────────────────────────────────

class TestRegisterRecent:
    def test_debounce_zero_skips(self):
        store, r = _make_store(debounce_ms=0)
        store.register_recent("L1", "fp1", "j1")
        r.set.assert_not_called()

    def test_calls_redis_set(self):
        store, r = _make_store(debounce_ms=200)
        store.register_recent("L1", "fp1", "j1")
        r.set.assert_called_once()
        call_args = r.set.call_args
        assert call_args.kwargs.get("px") == 200

    def test_exception_silent(self):
        store, r = _make_store(debounce_ms=200)
        r.set.side_effect = Exception("boom")
        store.register_recent("L1", "fp1", "j1")  # should not raise


# ── 8. recent_job ────────────────────────────────────────────────────────

class TestRecentJob:
    def test_debounce_zero_returns_none(self):
        store, _ = _make_store(debounce_ms=0)
        assert store.recent_job("L1", "fp1") is None

    def test_valid_match(self):
        store, r = _make_store(debounce_ms=100)
        r.get.return_value = json.dumps({"fp": "fp1", "job_id": "j1"})
        assert store.recent_job("L1", "fp1") == "j1"

    def test_fingerprint_mismatch(self):
        store, r = _make_store(debounce_ms=100)
        r.get.return_value = json.dumps({"fp": "other", "job_id": "j1"})
        assert store.recent_job("L1", "fp1") is None

    def test_invalid_json(self):
        store, r = _make_store(debounce_ms=100)
        r.get.return_value = "not-json"
        assert store.recent_job("L1", "fp1") is None

    def test_exception_returns_none(self):
        store, r = _make_store(debounce_ms=100)
        r.get.side_effect = Exception("boom")
        assert store.recent_job("L1", "fp1") is None

    def test_empty_raw_returns_none(self):
        store, r = _make_store(debounce_ms=100)
        r.get.return_value = None
        assert store.recent_job("L1", "fp1") is None

    def test_non_dict_json_returns_none(self):
        store, r = _make_store(debounce_ms=100)
        r.get.return_value = json.dumps([1, 2, 3])
        assert store.recent_job("L1", "fp1") is None

    def test_empty_job_id_returns_none(self):
        store, r = _make_store(debounce_ms=100)
        r.get.return_value = json.dumps({"fp": "fp1", "job_id": "  "})
        assert store.recent_job("L1", "fp1") is None


# ── 9. Alias ─────────────────────────────────────────────────────────────

def test_alias():
    assert mod.RedisLaneStore is mod.ChatRedisLaneStore
