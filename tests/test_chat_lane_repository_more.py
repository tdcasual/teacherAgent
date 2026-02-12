from __future__ import annotations

import json
import threading
from collections import deque
from types import SimpleNamespace

from services.api import chat_lane_repository as clr


def _base_state() -> SimpleNamespace:
    return SimpleNamespace(
        CHAT_JOB_LANES={},
        CHAT_JOB_ACTIVE_LANES=set(),
        CHAT_JOB_QUEUED=set(),
        CHAT_JOB_TO_LANE={},
        CHAT_LANE_CURSOR=[0],
        CHAT_LANE_RECENT={},
        CHAT_IDEMPOTENCY_STATE=None,
    )


def _install_state(monkeypatch, state: SimpleNamespace) -> None:
    monkeypatch.setattr(clr, "_get_state", lambda: state)


def _make_idempotency_state(tmp_path, request_index_text: str = "{}") -> SimpleNamespace:
    request_index_path = tmp_path / "request_index.json"
    request_index_path.write_text(request_index_text, encoding="utf-8")
    request_map_dir = tmp_path / "request_map"
    request_map_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        request_index_path=request_index_path,
        request_map_dir=request_map_dir,
        request_index_lock=threading.Lock(),
    )


def test_chat_last_user_text_skips_non_dict_and_non_user_entries():
    assert clr._chat_last_user_text("not-a-list") == ""

    messages = [
        {"role": "user", "content": "older-user-message"},
        {"role": "assistant", "content": "assistant-message"},
        "bad-entry",
    ]
    assert clr._chat_last_user_text(messages) == "older-user-message"


def test_resolve_chat_lane_id_unknown_role_uses_request_id(monkeypatch):
    monkeypatch.setattr(clr, "safe_fs_id", lambda value, prefix="": f"{prefix}-{value}")

    lane_id = clr.resolve_chat_lane_id("other", session_id="s1", request_id="r1")

    assert lane_id == "unknown:session-s1:req-r1"


def test_resolve_chat_lane_id_from_job_builds_from_request_payload(monkeypatch):
    captured = {}

    def _fake_resolve(role_hint, **kwargs):
        captured["role_hint"] = role_hint
        captured.update(kwargs)
        return "lane:resolved"

    monkeypatch.setattr(clr, "resolve_chat_lane_id", _fake_resolve)

    result = clr.resolve_chat_lane_id_from_job(
        {
            "request": {"role": "teacher", "student_id": "stu-1"},
            "teacher_id": "teacher-1",
            "session_id": "sess-1",
            "request_id": "req-1",
        }
    )

    assert result == "lane:resolved"
    assert captured == {
        "role_hint": "teacher",
        "session_id": "sess-1",
        "student_id": "stu-1",
        "teacher_id": "teacher-1",
        "request_id": "req-1",
    }


def test_chat_lane_store_forwards_configuration(monkeypatch):
    captured = {}

    def _fake_get_chat_lane_store(**kwargs):
        captured.update(kwargs)
        return "STORE"

    monkeypatch.setattr(clr, "get_chat_lane_store", _fake_get_chat_lane_store)

    store = clr._chat_lane_store()

    expected_tenant = str(clr.TENANT_ID or "default").strip() or "default"
    assert store == "STORE"
    assert captured["tenant_id"] == expected_tenant
    assert captured["is_pytest"] == clr._settings.is_pytest()
    assert captured["redis_url"] == clr.REDIS_URL
    assert captured["debounce_ms"] == clr.CHAT_LANE_DEBOUNCE_MS
    assert captured["claim_ttl_sec"] == clr.CHAT_JOB_CLAIM_TTL_SEC


def test_chat_find_position_locked_handles_missing_queue_and_non_pytest(monkeypatch):
    state = _base_state()
    _install_state(monkeypatch, state)

    monkeypatch.setattr(clr._settings, "is_pytest", lambda: True)
    assert clr._chat_find_position_locked("lane-1", "job-1") == 0

    state.CHAT_JOB_LANES["lane-1"] = deque(["job-a", "job-b"])
    assert clr._chat_find_position_locked("lane-1", "job-missing") == 0

    monkeypatch.setattr(clr._settings, "is_pytest", lambda: False)

    class _Store:
        def find_position(self, lane_id: str, job_id: str) -> int:
            assert lane_id == "lane-2"
            assert job_id == "job-2"
            return 9

    monkeypatch.setattr(clr, "_chat_lane_store", lambda: _Store())
    assert clr._chat_find_position_locked("lane-2", "job-2") == 9


def test_chat_enqueue_locked_returns_existing_position_for_duplicate(monkeypatch):
    state = _base_state()
    state.CHAT_JOB_QUEUED.add("job-1")
    _install_state(monkeypatch, state)
    monkeypatch.setattr(clr, "_chat_find_position_locked", lambda lane_id, job_id: 7)

    assert clr._chat_enqueue_locked("job-1", "lane-1") == 7


def test_chat_has_pending_locked_reflects_queue_content(monkeypatch):
    state = _base_state()
    state.CHAT_JOB_LANES = {
        "lane-empty": deque(),
        "lane-busy": deque(["job-1"]),
    }
    _install_state(monkeypatch, state)

    assert clr._chat_has_pending_locked() is True

    state.CHAT_JOB_LANES["lane-busy"].clear()
    assert clr._chat_has_pending_locked() is False


def test_chat_pick_next_locked_skips_active_lane_and_updates_state(monkeypatch):
    state = _base_state()
    state.CHAT_JOB_LANES = {
        "lane-a": deque(["job-a"]),
        "lane-b": deque(["job-b"]),
    }
    state.CHAT_JOB_ACTIVE_LANES = {"lane-a"}
    state.CHAT_JOB_QUEUED = {"job-a", "job-b"}
    state.CHAT_LANE_CURSOR = [0]
    _install_state(monkeypatch, state)

    job_id, lane_id = clr._chat_pick_next_locked()

    assert (job_id, lane_id) == ("job-b", "lane-b")
    assert "job-b" not in state.CHAT_JOB_QUEUED
    assert "lane-b" in state.CHAT_JOB_ACTIVE_LANES
    assert state.CHAT_JOB_TO_LANE["job-b"] == "lane-b"


def test_chat_pick_next_locked_returns_empty_when_all_non_empty_lanes_are_active(monkeypatch):
    state = _base_state()
    state.CHAT_JOB_LANES = {"lane-a": deque(["job-a"])}
    state.CHAT_JOB_ACTIVE_LANES = {"lane-a"}
    _install_state(monkeypatch, state)

    assert clr._chat_pick_next_locked() == ("", "")


def test_chat_mark_done_locked_clears_lane_and_mappings(monkeypatch):
    state = _base_state()
    state.CHAT_JOB_ACTIVE_LANES = {"lane-a"}
    state.CHAT_JOB_TO_LANE = {"job-a": "lane-a"}
    state.CHAT_JOB_LANES = {"lane-a": deque()}
    _install_state(monkeypatch, state)

    clr._chat_mark_done_locked("job-a", "lane-a")

    assert "lane-a" not in state.CHAT_JOB_ACTIVE_LANES
    assert "job-a" not in state.CHAT_JOB_TO_LANE
    assert "lane-a" not in state.CHAT_JOB_LANES


def test_chat_register_recent_locked_uses_store_outside_pytest(monkeypatch):
    state = _base_state()
    _install_state(monkeypatch, state)
    monkeypatch.setattr(clr._settings, "is_pytest", lambda: False)

    calls = {}

    class _Store:
        def register_recent(self, lane_id: str, fingerprint: str, job_id: str) -> None:
            calls["args"] = (lane_id, fingerprint, job_id)

    monkeypatch.setattr(clr, "_chat_lane_store", lambda: _Store())

    clr._chat_register_recent_locked("lane-a", "fp-a", "job-a")

    assert calls["args"] == ("lane-a", "fp-a", "job-a")


def test_chat_recent_job_locked_handles_mismatch_and_expiry(monkeypatch):
    state = _base_state()
    _install_state(monkeypatch, state)
    monkeypatch.setattr(clr._settings, "is_pytest", lambda: True)
    monkeypatch.setattr(clr, "CHAT_LANE_DEBOUNCE_MS", 1000)

    state.CHAT_LANE_RECENT["lane-a"] = (1000.0, "fp-a", "job-a")

    monkeypatch.setattr(clr.time, "time", lambda: 1000.0)
    assert clr._chat_recent_job_locked("lane-a", "fp-b") is None

    monkeypatch.setattr(clr.time, "time", lambda: 1003.0)
    assert clr._chat_recent_job_locked("lane-a", "fp-a") is None


def test_chat_recent_job_locked_uses_store_outside_pytest(monkeypatch):
    state = _base_state()
    _install_state(monkeypatch, state)
    monkeypatch.setattr(clr._settings, "is_pytest", lambda: False)

    class _Store:
        def recent_job(self, lane_id: str, fingerprint: str):
            assert lane_id == "lane-a"
            assert fingerprint == "fp-a"
            return "job-from-store"

    monkeypatch.setattr(clr, "_chat_lane_store", lambda: _Store())

    assert clr._chat_recent_job_locked("lane-a", "fp-a") == "job-from-store"


def test_load_chat_request_index_handles_corrupt_json(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path, request_index_text="{bad")
    _install_state(monkeypatch, state)

    assert clr.load_chat_request_index() == {}


def test_load_chat_request_index_handles_non_dict_payload(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path, request_index_text=json.dumps([1, 2, 3]))
    _install_state(monkeypatch, state)

    assert clr.load_chat_request_index() == {}


def test_chat_request_map_get_rejects_blank_request_id(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    assert clr._chat_request_map_get("   ") is None


def test_chat_request_map_get_rejects_empty_job_id(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    request_path = clr._chat_request_map_path("req-empty")
    assert request_path is not None
    request_path.write_text("   ", encoding="utf-8")

    assert clr._chat_request_map_get("req-empty") is None


def test_chat_request_map_get_removes_stale_mapping(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    request_id = "req-stale"
    request_path = clr._chat_request_map_path(request_id)
    assert request_path is not None
    request_path.write_text("job-missing", encoding="utf-8")

    monkeypatch.setattr(clr, "_chat_job_path", lambda job_id: tmp_path / "jobs" / job_id)

    assert clr._chat_request_map_get(request_id) is None
    assert not request_path.exists()


def test_chat_request_map_get_returns_job_when_stale_cleanup_raises(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    request_id = "req-keep"
    request_path = clr._chat_request_map_path(request_id)
    assert request_path is not None
    request_path.write_text("job-keep", encoding="utf-8")

    def _raise_chat_job_path(_job_id: str):
        raise RuntimeError("path failed")

    monkeypatch.setattr(clr, "_chat_job_path", _raise_chat_job_path)

    assert clr._chat_request_map_get(request_id) == "job-keep"


def test_chat_request_map_set_if_absent_rejects_blank_values(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    assert clr._chat_request_map_set_if_absent("", "job-1") is False
    assert clr._chat_request_map_set_if_absent("req-1", "") is False


def test_chat_request_map_set_if_absent_handles_open_exception(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    def _raise_open(*_args, **_kwargs):
        raise OSError("open failed")

    monkeypatch.setattr(clr.os, "open", _raise_open)

    assert clr._chat_request_map_set_if_absent("req-1", "job-1") is False


def test_chat_request_map_set_if_absent_ignores_close_failure(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    monkeypatch.setattr(clr.os, "open", lambda *_args, **_kwargs: 42)
    monkeypatch.setattr(clr.os, "write", lambda _fd, payload: len(payload))
    monkeypatch.setattr(clr.os, "fsync", lambda _fd: None)

    def _raise_close(_fd: int) -> None:
        raise OSError("close failed")

    monkeypatch.setattr(clr.os, "close", _raise_close)

    assert clr._chat_request_map_set_if_absent("req-1", "job-1") is True


def test_upsert_chat_request_index_handles_legacy_write_failure(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    monkeypatch.setattr(clr, "_chat_request_map_set_if_absent", lambda request_id, job_id: True)

    def _raise_atomic_write(*_args, **_kwargs):
        raise RuntimeError("atomic write failed")

    monkeypatch.setattr(clr, "_atomic_write_json", _raise_atomic_write)

    clr.upsert_chat_request_index("req-1", "job-1")


def test_get_chat_job_id_by_request_handles_legacy_read_failure(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    monkeypatch.setattr(clr, "_chat_request_map_get", lambda request_id: None)

    def _raise_load() -> dict:
        raise RuntimeError("load failed")

    monkeypatch.setattr(clr, "load_chat_request_index", _raise_load)

    assert clr.get_chat_job_id_by_request("req-1") is None


def test_get_chat_job_id_by_request_returns_none_for_missing_legacy_job(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(
        tmp_path,
        request_index_text=json.dumps({"req-1": "job-missing"}),
    )
    _install_state(monkeypatch, state)

    monkeypatch.setattr(clr, "_chat_request_map_get", lambda request_id: None)
    monkeypatch.setattr(clr, "_chat_job_path", lambda job_id: tmp_path / "jobs" / str(job_id))

    assert clr.get_chat_job_id_by_request("req-1") is None


def test_get_chat_job_id_by_request_handles_job_path_exception(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(
        tmp_path,
        request_index_text=json.dumps({"req-1": "job-any"}),
    )
    _install_state(monkeypatch, state)

    monkeypatch.setattr(clr, "_chat_request_map_get", lambda request_id: None)

    def _raise_chat_job_path(_job_id: str):
        raise RuntimeError("bad job path")

    monkeypatch.setattr(clr, "_chat_job_path", _raise_chat_job_path)

    assert clr.get_chat_job_id_by_request("req-1") is None


def test_chat_job_path_uses_app_core_chat_job_path(tmp_path, monkeypatch):
    from services.api import app_core

    monkeypatch.setattr(app_core, "chat_job_path", lambda job_id: tmp_path / "jobs" / job_id)
    assert clr._chat_job_path("job-1") == tmp_path / "jobs" / "job-1"


def test_chat_last_user_text_returns_empty_when_no_user_message():
    assert clr._chat_last_user_text([{"role": "assistant", "content": "hello"}]) == ""


def test_chat_text_fingerprint_normalizes_whitespace_and_case():
    left = clr._chat_text_fingerprint("Hello   WORLD")
    right = clr._chat_text_fingerprint(" hello world ")
    assert left == right


def test_resolve_chat_lane_id_student_and_teacher(monkeypatch):
    monkeypatch.setattr(clr, "safe_fs_id", lambda value, prefix="": f"{prefix}-{value}")
    monkeypatch.setattr(clr, "resolve_teacher_id", lambda teacher_id: f"teacher-{teacher_id}")

    student_lane = clr.resolve_chat_lane_id("student", session_id="s1", student_id="stu-1")
    teacher_lane = clr.resolve_chat_lane_id("teacher", session_id="s2", teacher_id="t-1")

    assert student_lane == "student:student-stu-1:session-s1"
    assert teacher_lane == "teacher:teacher-t-1:session-s2"


def test_resolve_chat_lane_id_from_job_prefers_explicit_lane():
    assert clr.resolve_chat_lane_id_from_job({"lane_id": "lane-explicit"}) == "lane-explicit"


def test_chat_lane_load_locked_pytest_branch(monkeypatch):
    state = _base_state()
    state.CHAT_JOB_LANES = {"lane-1": deque(["job-1", "job-2"])}
    state.CHAT_JOB_ACTIVE_LANES = {"lane-1"}
    _install_state(monkeypatch, state)
    monkeypatch.setattr(clr._settings, "is_pytest", lambda: True)

    load = clr._chat_lane_load_locked("lane-1")
    assert load == {"queued": 2, "active": 1, "total": 3}


def test_chat_find_position_locked_returns_index_when_found(monkeypatch):
    state = _base_state()
    state.CHAT_JOB_LANES = {"lane-1": deque(["job-1", "job-2"])}
    _install_state(monkeypatch, state)
    monkeypatch.setattr(clr._settings, "is_pytest", lambda: True)

    assert clr._chat_find_position_locked("lane-1", "job-2") == 2


def test_chat_enqueue_locked_adds_new_job_and_updates_indexes(monkeypatch):
    state = _base_state()
    _install_state(monkeypatch, state)

    position = clr._chat_enqueue_locked("job-1", "lane-1")

    assert position == 1
    assert list(state.CHAT_JOB_LANES["lane-1"]) == ["job-1"]
    assert "job-1" in state.CHAT_JOB_QUEUED
    assert state.CHAT_JOB_TO_LANE["job-1"] == "lane-1"


def test_chat_pick_next_locked_handles_queue_disappearing_after_snapshot(monkeypatch):
    class _LaneMap(dict):
        def items(self):
            return [("lane-1", deque(["job-1"]))]

        def get(self, key, default=None):
            assert key == "lane-1"
            return deque()

    state = _base_state()
    state.CHAT_JOB_LANES = _LaneMap()
    _install_state(monkeypatch, state)

    assert clr._chat_pick_next_locked() == ("", "")


def test_chat_register_recent_locked_pytest_branch(monkeypatch):
    state = _base_state()
    _install_state(monkeypatch, state)
    monkeypatch.setattr(clr._settings, "is_pytest", lambda: True)
    monkeypatch.setattr(clr.time, "time", lambda: 1234.5)

    clr._chat_register_recent_locked("lane-1", "fp-1", "job-1")
    assert state.CHAT_LANE_RECENT["lane-1"] == (1234.5, "fp-1", "job-1")


def test_chat_recent_job_locked_handles_debounce_disabled_missing_and_match(monkeypatch):
    state = _base_state()
    _install_state(monkeypatch, state)
    monkeypatch.setattr(clr._settings, "is_pytest", lambda: True)

    monkeypatch.setattr(clr, "CHAT_LANE_DEBOUNCE_MS", 0)
    assert clr._chat_recent_job_locked("lane-1", "fp-1") is None

    monkeypatch.setattr(clr, "CHAT_LANE_DEBOUNCE_MS", 1000)
    assert clr._chat_recent_job_locked("lane-1", "fp-1") is None

    state.CHAT_LANE_RECENT["lane-1"] = (1000.0, "fp-1", "job-1")
    monkeypatch.setattr(clr.time, "time", lambda: 1000.5)
    assert clr._chat_recent_job_locked("lane-1", "fp-1") == "job-1"


def test_load_chat_request_index_handles_missing_file(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = SimpleNamespace(
        request_index_path=tmp_path / "missing.json",
        request_map_dir=tmp_path / "request_map",
        request_index_lock=threading.Lock(),
    )
    state.CHAT_IDEMPOTENCY_STATE.request_map_dir.mkdir(parents=True, exist_ok=True)
    _install_state(monkeypatch, state)

    assert clr.load_chat_request_index() == {}


def test_chat_request_map_get_handles_missing_map_file(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    assert clr._chat_request_map_get("req-missing-file") is None


def test_chat_request_map_set_if_absent_returns_false_when_file_exists(tmp_path, monkeypatch):
    state = _base_state()
    state.CHAT_IDEMPOTENCY_STATE = _make_idempotency_state(tmp_path)
    _install_state(monkeypatch, state)

    path = clr._chat_request_map_path("req-1")
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("existing", encoding="utf-8")

    assert clr._chat_request_map_set_if_absent("req-1", "job-1") is False


def test_get_chat_job_id_by_request_returns_primary_request_map_value(monkeypatch):
    monkeypatch.setattr(clr, "_chat_request_map_get", lambda request_id: "job-direct")
    assert clr.get_chat_job_id_by_request("req-1") == "job-direct"
