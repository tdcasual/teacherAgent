"""Tests for session_store.py Phase 2 fixes."""
from __future__ import annotations

import json
import threading

import pytest


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr("services.api.session_store.SESSION_INDEX_MAX_ITEMS", 100)
    yield


# ---------------------------------------------------------------------------
# TOCTOU fix: index loaders handle missing file without exists() check
# ---------------------------------------------------------------------------

def test_load_student_sessions_index_missing_file(tmp_path, monkeypatch):
    from services.api.session_store import load_student_sessions_index

    monkeypatch.setattr(
        "services.api.session_store.student_sessions_index_path",
        lambda sid: tmp_path / "nonexistent.json",
    )
    assert load_student_sessions_index("s1") == []


def test_load_teacher_sessions_index_missing_file(tmp_path, monkeypatch):
    from services.api.session_store import load_teacher_sessions_index

    monkeypatch.setattr(
        "services.api.session_store.teacher_sessions_index_path",
        lambda tid: tmp_path / "nonexistent.json",
    )
    assert load_teacher_sessions_index("t1") == []


def test_load_student_sessions_index_corrupt_json(tmp_path, monkeypatch):
    from services.api.session_store import load_student_sessions_index

    bad = tmp_path / "corrupt.json"
    bad.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(
        "services.api.session_store.student_sessions_index_path",
        lambda sid: bad,
    )
    assert load_student_sessions_index("s1") == []


# ---------------------------------------------------------------------------
# Meta protection: reserved keys (ts, role, content) not overwritten
# ---------------------------------------------------------------------------

def test_append_student_meta_does_not_overwrite_core_fields(tmp_path, monkeypatch):
    from services.api.session_store import append_student_session_message

    monkeypatch.setattr(
        "services.api.session_store.student_sessions_base_dir",
        lambda sid: tmp_path,
    )
    out = tmp_path / "session.jsonl"
    monkeypatch.setattr(
        "services.api.session_store.student_session_file",
        lambda sid, ssid: out,
    )
    append_student_session_message(
        "s1", "sess1", "user", "hello",
        meta={"ts": "EVIL", "role": "EVIL", "content": "EVIL", "extra": "ok"},
    )
    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["role"] == "user"
    assert rec["content"] == "hello"
    assert rec["ts"] != "EVIL"
    assert rec["extra"] == "ok"


def test_append_teacher_meta_does_not_overwrite_core_fields(tmp_path, monkeypatch):
    from services.api.session_store import append_teacher_session_message

    monkeypatch.setattr(
        "services.api.session_store.teacher_sessions_base_dir",
        lambda tid: tmp_path,
    )
    out = tmp_path / "session.jsonl"
    monkeypatch.setattr(
        "services.api.session_store.teacher_session_file",
        lambda tid, ssid: out,
    )
    append_teacher_session_message(
        "t1", "sess1", "assistant", "hi",
        meta={"ts": "EVIL", "role": "EVIL", "content": "EVIL", "tag": "v1"},
    )
    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["role"] == "assistant"
    assert rec["content"] == "hi"
    assert rec["ts"] != "EVIL"
    assert rec["tag"] == "v1"


# ---------------------------------------------------------------------------
# Fsync: append writes are flushed (verify file is non-empty after write)
# ---------------------------------------------------------------------------

def test_append_student_message_persists(tmp_path, monkeypatch):
    from services.api.session_store import append_student_session_message

    monkeypatch.setattr(
        "services.api.session_store.student_sessions_base_dir",
        lambda sid: tmp_path,
    )
    out = tmp_path / "session.jsonl"
    monkeypatch.setattr(
        "services.api.session_store.student_session_file",
        lambda sid, ssid: out,
    )
    append_student_session_message("s1", "sess1", "user", "test message")
    assert out.exists()
    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["content"] == "test message"
    assert rec["role"] == "user"


# ---------------------------------------------------------------------------
# job_repository: type validation on load
# ---------------------------------------------------------------------------

def test_load_upload_job_rejects_non_dict(tmp_path, monkeypatch):
    from services.api.job_repository import load_upload_job

    monkeypatch.setattr(
        "services.api.job_repository.upload_job_path",
        lambda jid: tmp_path / jid,
    )
    job_dir = tmp_path / "j1"
    job_dir.mkdir()
    (job_dir / "job.json").write_text('"just a string"', encoding="utf-8")
    with pytest.raises(ValueError, match="not a JSON object"):
        load_upload_job("j1")


def test_load_exam_job_rejects_non_dict(tmp_path, monkeypatch):
    from services.api.job_repository import load_exam_job

    monkeypatch.setattr(
        "services.api.job_repository.exam_job_path",
        lambda jid: tmp_path / jid,
    )
    job_dir = tmp_path / "e1"
    job_dir.mkdir()
    (job_dir / "job.json").write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(ValueError, match="not a JSON object"):
        load_exam_job("e1")


def test_write_upload_job_logs_corrupt_json(tmp_path, monkeypatch, caplog):
    from services.api.job_repository import write_upload_job

    monkeypatch.setattr(
        "services.api.job_repository.upload_job_path",
        lambda jid: tmp_path / jid,
    )
    job_dir = tmp_path / "j2"
    job_dir.mkdir()
    (job_dir / "job.json").write_text("{bad json", encoding="utf-8")
    import logging
    with caplog.at_level(logging.WARNING, logger="services.api.job_repository"):
        result = write_upload_job("j2", {"status": "ok"})
    assert result["status"] == "ok"
    assert "corrupt" in caplog.text.lower() or "resetting" in caplog.text.lower()


# ---------------------------------------------------------------------------
# chat_lane_repository: null guard on CHAT_IDEMPOTENCY_STATE
# ---------------------------------------------------------------------------

def _clr_state_none(monkeypatch):
    """Patch _get_state() to return an object with CHAT_IDEMPOTENCY_STATE=None."""
    from types import SimpleNamespace

    from services.api import chat_lane_repository as clr
    fake = SimpleNamespace(CHAT_IDEMPOTENCY_STATE=None)
    monkeypatch.setattr(clr, "_get_state", lambda: fake)
    return clr


def test_load_chat_request_index_returns_empty_when_state_none(monkeypatch):
    clr = _clr_state_none(monkeypatch)
    assert clr.load_chat_request_index() == {}


def test_chat_request_map_path_returns_none_when_state_none(monkeypatch):
    clr = _clr_state_none(monkeypatch)
    assert clr._chat_request_map_path("req1") is None


def test_chat_request_map_get_returns_none_when_state_none(monkeypatch):
    clr = _clr_state_none(monkeypatch)
    assert clr._chat_request_map_get("req1") is None


def test_upsert_chat_request_index_noop_when_state_none(monkeypatch):
    clr = _clr_state_none(monkeypatch)
    # Should not raise
    clr.upsert_chat_request_index("req1", "job1")


def test_get_chat_job_id_by_request_returns_none_when_state_none(monkeypatch):
    clr = _clr_state_none(monkeypatch)
    assert clr.get_chat_job_id_by_request("req1") is None


def test_get_chat_job_id_by_request_returns_legacy_when_primary_map_misses(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from services.api import chat_lane_repository as clr

    request_index_path = tmp_path / "request_index.json"
    request_index_path.write_text(json.dumps({"req_legacy": "job_legacy"}), encoding="utf-8")
    request_map_dir = tmp_path / "request_map"
    request_map_dir.mkdir(parents=True, exist_ok=True)

    state = SimpleNamespace(
        CHAT_IDEMPOTENCY_STATE=SimpleNamespace(
            request_index_path=request_index_path,
            request_map_dir=request_map_dir,
            request_index_lock=threading.Lock(),
        )
    )
    monkeypatch.setattr(clr, "_get_state", lambda: state)
    monkeypatch.setattr(clr, "_chat_request_map_get", lambda request_id: None)
    monkeypatch.setattr(clr, "_chat_job_path", lambda job_id: tmp_path / "jobs" / str(job_id))

    legacy_job_dir = tmp_path / "jobs" / "job_legacy"
    legacy_job_dir.mkdir(parents=True, exist_ok=True)
    (legacy_job_dir / "job.json").write_text("{}", encoding="utf-8")

    assert clr.get_chat_job_id_by_request("req_legacy") == "job_legacy"


# ---------------------------------------------------------------------------
# compaction helpers: _teacher_compact_reset_ts
# ---------------------------------------------------------------------------

def test_compact_reset_ts_allows_immediate_retry(monkeypatch):
    from services.api import teacher_session_compaction_helpers as tsch

    monkeypatch.setattr(tsch, "TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC", 3600)
    monkeypatch.setattr(tsch, "_TEACHER_SESSION_COMPACT_TS", {})
    # First call should be allowed
    assert tsch._teacher_compact_allowed("t1", "s1") is True
    # Second call should be blocked (within interval)
    assert tsch._teacher_compact_allowed("t1", "s1") is False
    # Reset the timestamp
    tsch._teacher_compact_reset_ts("t1", "s1")
    # Now should be allowed again
    assert tsch._teacher_compact_allowed("t1", "s1") is True


# ---------------------------------------------------------------------------
# compaction helpers: unbounded dict eviction
# ---------------------------------------------------------------------------

def test_compact_ts_evicts_when_over_max(monkeypatch):
    from services.api import teacher_session_compaction_helpers as tsch

    monkeypatch.setattr(tsch, "TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC", 0)
    monkeypatch.setattr(tsch, "_COMPACT_TS_MAX_SIZE", 5)
    ts_dict = {}
    monkeypatch.setattr(tsch, "_TEACHER_SESSION_COMPACT_TS", ts_dict)
    # Fill beyond max
    monkeypatch.setattr(tsch, "TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC", 1)
    import time
    for i in range(10):
        ts_dict[f"key_{i}"] = time.time() - (10 - i)
    # Trigger eviction by calling _teacher_compact_allowed with a new key
    monkeypatch.setattr(tsch, "TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC", 1)
    tsch._teacher_compact_allowed("new_teacher", "new_session")
    # Dict should have been pruned
    assert len(ts_dict) <= 7  # 10/2 evicted + 1 new = ~6
