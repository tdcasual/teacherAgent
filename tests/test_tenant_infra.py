"""Tests for tenant infrastructure layer fixes (Phase 3 audit)."""
from __future__ import annotations

import fcntl
import gc
import json
import os
import sqlite3
import threading
import weakref
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeConfig:
    def __init__(self, tid, enabled=True, extra=None):
        self.tenant_id = tid
        self.enabled = enabled
        self.data_dir = "/tmp/test_data"
        self.uploads_dir = "/tmp/test_uploads"
        self.extra = extra or {}

class _FakeStore:
    def __init__(self, configs: Dict[str, _FakeConfig]):
        self._configs = configs
    def get(self, tid):
        return self._configs.get(tid)


# ---------------------------------------------------------------------------
# 1. tenant_registry: TOCTOU race fix
# ---------------------------------------------------------------------------

def test_registry_single_create_under_contention():
    from services.api.tenant_registry import TenantRegistry
    store = _FakeStore({"t1": _FakeConfig("t1")})
    registry = TenantRegistry(store)
    create_count = [0]

    def _fake_create(settings):
        create_count[0] += 1
        inst = MagicMock()
        inst.app = MagicMock()
        return inst

    with patch("services.api.tenant_registry.create_tenant_app", side_effect=_fake_create):
        threads = [threading.Thread(target=registry.get_or_create, args=("t1",)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
    assert create_count[0] == 1


def test_registry_disabled_tenant_raises():
    from services.api.tenant_registry import TenantRegistry
    store = _FakeStore({"t1": _FakeConfig("t1", enabled=False)})
    registry = TenantRegistry(store)
    with pytest.raises(KeyError, match="tenant_not_found"):
        registry.get_or_create("t1")


def test_registry_missing_tenant_raises():
    from services.api.tenant_registry import TenantRegistry
    store = _FakeStore({})
    registry = TenantRegistry(store)
    with pytest.raises(KeyError, match="tenant_not_found"):
        registry.get_or_create("missing")


def test_validate_tenant_id_rejects_bad_input():
    from services.api.tenant_registry import validate_tenant_id
    for bad in ["", "a" * 65, "bad/id", "../up"]:
        with pytest.raises(ValueError):
            validate_tenant_id(bad)


# ---------------------------------------------------------------------------
# 2. tenant_dispatcher: tightened regex
# ---------------------------------------------------------------------------

def test_dispatcher_regex_rejects_long_id():
    from services.api.tenant_dispatcher import _split_tenant_path
    assert _split_tenant_path("/t/" + "a" * 64 + "/foo") is not None
    assert _split_tenant_path("/t/" + "a" * 65 + "/foo") is None


def test_dispatcher_regex_rejects_special_chars():
    from services.api.tenant_dispatcher import _split_tenant_path
    assert _split_tenant_path("/t/../../etc/passwd/foo") is None
    assert _split_tenant_path("/t/tenant%20id/foo") is None


def test_dispatcher_regex_accepts_valid():
    from services.api.tenant_dispatcher import _split_tenant_path
    assert _split_tenant_path("/t/my-tenant_01/api/chat") == ("my-tenant_01", "/api/chat")


# ---------------------------------------------------------------------------
# 3. wiring: CURRENT_CORE strict mode
# ---------------------------------------------------------------------------

def test_get_app_core_raises_in_multi_tenant():
    from services.api.wiring import CURRENT_CORE, get_app_core
    token = CURRENT_CORE.set(None)
    try:
        with patch.dict(os.environ, {"MULTI_TENANT_ENABLED": "1"}):
            with pytest.raises(RuntimeError, match="tenant context is required"):
                get_app_core()
    finally:
        CURRENT_CORE.reset(token)


def test_get_app_core_fallback_single_tenant():
    from services.api.wiring import CURRENT_CORE, get_app_core
    token = CURRENT_CORE.set(None)
    try:
        env = os.environ.copy()
        env.pop("MULTI_TENANT_ENABLED", None)
        with patch.dict(os.environ, env, clear=True):
            mod = get_app_core()
            assert mod is not None
    finally:
        CURRENT_CORE.reset(token)


# ---------------------------------------------------------------------------
# 4. chat_lane_store_factory: thread-safe creation
# ---------------------------------------------------------------------------

def test_chat_lane_store_factory_thread_safe():
    from services.api.chat_lane_store_factory import get_chat_lane_store, reset_chat_lane_stores
    reset_chat_lane_stores()
    results = []

    def _get():
        store = get_chat_lane_store(
            tenant_id="test", is_pytest=True, redis_url="", debounce_ms=0, claim_ttl_sec=30,
        )
        results.append(id(store))

    threads = [threading.Thread(target=_get) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(set(results)) == 1
    reset_chat_lane_stores()


# ---------------------------------------------------------------------------
# 5. queue_backend_factory: per-tenant isolation
# ---------------------------------------------------------------------------

def test_queue_backend_per_tenant():
    from services.api.queue.queue_backend_factory import get_app_queue_backend, reset_queue_backend
    reset_queue_backend()
    ba = get_app_queue_backend(tenant_id="a", is_pytest=True, inline_backend_factory=lambda: MagicMock(name="a"))
    bb = get_app_queue_backend(tenant_id="b", is_pytest=True, inline_backend_factory=lambda: MagicMock(name="b"))
    assert ba is not bb
    ba2 = get_app_queue_backend(tenant_id="a", is_pytest=True, inline_backend_factory=lambda: MagicMock())
    assert ba2 is ba
    reset_queue_backend()


# ---------------------------------------------------------------------------
# 6. tenant_config_store: logging on corrupt JSON
# ---------------------------------------------------------------------------

def test_config_store_logs_corrupt_json(tmp_path):
    from services.api.tenant_config_store import TenantConfigStore
    db_path = tmp_path / "tenants.sqlite3"
    store = TenantConfigStore(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO tenants (tenant_id, data_dir, uploads_dir, enabled, updated_at, extra_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("bad", "/data", "/uploads", 1, "2026-01-01", "{invalid json}"),
    )
    conn.commit()
    conn.close()
    with patch("services.api.tenant_config_store._log") as mock_log:
        cfg = store.get("bad")
        assert cfg is not None
        assert cfg.extra == {}
        mock_log.warning.assert_called_once()


# ---------------------------------------------------------------------------
# 7. tenant_admin_api: path traversal guard
# ---------------------------------------------------------------------------

def test_path_traversal_guard_blocks():
    from services.api.tenant_admin_api import _validate_tenant_path
    from fastapi import HTTPException
    with patch.dict(os.environ, {"TENANT_DATA_BASE_DIR": "/data/tenants"}):
        with pytest.raises(HTTPException) as exc_info:
            _validate_tenant_path("/etc/passwd", "data_dir")
        assert exc_info.value.status_code == 400


def test_path_traversal_guard_allows_without_base():
    from services.api.tenant_admin_api import _validate_tenant_path
    os.environ.pop("TENANT_DATA_BASE_DIR", None)
    result = _validate_tenant_path("/any/path", "data_dir")
    assert result


# ---------------------------------------------------------------------------
# 8. job_repository: file lock for read-modify-write
# ---------------------------------------------------------------------------

def test_write_upload_job_creates_lock_file(tmp_path):
    from services.api.job_repository import write_upload_job
    job_id = "lock_test"
    with patch("services.api.job_repository.upload_job_path", return_value=tmp_path / job_id):
        write_upload_job(job_id, {"status": "pending"}, overwrite=True)
    assert (tmp_path / job_id / ".job.lock").exists()


def test_write_upload_job_merges(tmp_path):
    from services.api.job_repository import write_upload_job
    job_id = "merge_test"
    with patch("services.api.job_repository.upload_job_path", return_value=tmp_path / job_id):
        write_upload_job(job_id, {"a": 1}, overwrite=True)
        result = write_upload_job(job_id, {"b": 2})
    assert result["a"] == 1
    assert result["b"] == 2


def test_write_upload_job_concurrent(tmp_path):
    from services.api.job_repository import write_upload_job
    job_id = "conc"
    job_dir = tmp_path / job_id
    with patch("services.api.job_repository.upload_job_path", return_value=job_dir):
        write_upload_job(job_id, {"x": 0}, overwrite=True)
    errors = []
    def _run():
        try:
            for _ in range(5):
                with patch("services.api.job_repository.upload_job_path", return_value=job_dir):
                    write_upload_job(job_id, {})
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert not errors


# ---------------------------------------------------------------------------
# 9. session_store: WeakValueDictionary
# ---------------------------------------------------------------------------

def test_session_locks_are_weak():
    from services.api import session_store
    assert isinstance(session_store._SESSION_INDEX_LOCKS, weakref.WeakValueDictionary)


def test_session_lock_gc():
    from services.api.session_store import _session_index_lock, _SESSION_INDEX_LOCKS
    fake = Path("/tmp/_test_gc_lock_unique/index.json")
    lock = _session_index_lock(fake)
    key = str(fake.resolve())
    assert key in _SESSION_INDEX_LOCKS
    del lock
    gc.collect()
    assert key not in _SESSION_INDEX_LOCKS


# ---------------------------------------------------------------------------
# 10. CHAT_LANE_CURSOR: mutable container (now on app_core, accessed via get_app_core)
# ---------------------------------------------------------------------------

def test_cursor_is_mutable_list():
    from services.api import app as app_mod
    assert isinstance(app_mod.CHAT_LANE_CURSOR, list) and len(app_mod.CHAT_LANE_CURSOR) == 1


def test_cursor_shared_reference():
    from services.api import app as app_mod
    ref = app_mod.CHAT_LANE_CURSOR
    orig = app_mod.CHAT_LANE_CURSOR[0]
    app_mod.CHAT_LANE_CURSOR[0] = 99
    assert ref[0] == 99
    app_mod.CHAT_LANE_CURSOR[0] = orig


# ---------------------------------------------------------------------------
# 11. rq_tenant_runtime: double-checked locking
# ---------------------------------------------------------------------------

def test_rq_runtime_thread_safe():
    import services.api.workers.rq_tenant_runtime as rq_mod
    rq_mod._TENANT_REGISTRY = None
    results = []
    def _get():
        try:
            results.append(id(rq_mod._get_registry()))
        except Exception:
            pass
    with patch.object(rq_mod, "TenantConfigStore") as mc1:
        mc1.return_value = MagicMock()
        with patch.object(rq_mod, "TenantRegistry") as mc2:
            mc2.return_value = MagicMock()
            threads = [threading.Thread(target=_get) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
    assert len(set(results)) == 1
    rq_mod._TENANT_REGISTRY = None


# ---------------------------------------------------------------------------
# 12. tenant_app_factory: shutdown logs errors
# ---------------------------------------------------------------------------

def test_shutdown_logs_error():
    import types as _types
    from services.api.tenant_app_factory import TenantAppInstance
    mod = _types.ModuleType("test_mod")
    mod._APP_CORE = None
    inst = TenantAppInstance(tenant_id="t1", module_name="test_mod", module=mod, app=MagicMock())
    with patch("services.api.runtime.bootstrap.stop_runtime", side_effect=RuntimeError("boom")):
        with patch("services.api.tenant_app_factory._log") as ml:
            inst.shutdown()
            ml.warning.assert_called_once()


# ---------------------------------------------------------------------------
# 13. Extracted module reset functions
# ---------------------------------------------------------------------------

def test_reset_session_locks():
    from services.api import session_store as ss
    old_locks = ss._SESSION_INDEX_LOCKS
    old_lock = ss._SESSION_INDEX_LOCKS_LOCK
    ss.reset_session_locks()
    assert ss._SESSION_INDEX_LOCKS is not old_locks
    assert ss._SESSION_INDEX_LOCKS_LOCK is not old_lock
    assert isinstance(ss._SESSION_INDEX_LOCKS, weakref.WeakValueDictionary)


def test_reset_profile_cache():
    from services.api import profile_service as ps
    ps._PROFILE_CACHE["test"] = "value"
    ps.reset_profile_cache()
    assert ps._PROFILE_CACHE == {}
    assert hasattr(ps._PROFILE_CACHE_LOCK, "acquire")


def test_reset_assignment_cache():
    from services.api import assignment_data_service as ads
    ads._ASSIGNMENT_DETAIL_CACHE["test"] = "value"
    ads.reset_assignment_cache()
    assert ads._ASSIGNMENT_DETAIL_CACHE == {}
    assert hasattr(ads._ASSIGNMENT_DETAIL_CACHE_LOCK, "acquire")


def test_reset_compact_state():
    from services.api import teacher_session_compaction_helpers as tsch
    tsch._TEACHER_SESSION_COMPACT_TS["test"] = 1.0
    tsch.reset_compact_state()
    assert tsch._TEACHER_SESSION_COMPACT_TS == {}
    assert hasattr(tsch._TEACHER_SESSION_COMPACT_LOCK, "acquire")


# ---------------------------------------------------------------------------
# 14. chat_lane_repository uses get_app_core() for state
# ---------------------------------------------------------------------------

def test_chat_lane_repo_get_state_returns_app_core():
    from services.api import chat_lane_repository as clr
    _ac = clr._get_state()
    assert hasattr(_ac, "CHAT_JOB_LANES")
    assert hasattr(_ac, "CHAT_IDEMPOTENCY_STATE")
