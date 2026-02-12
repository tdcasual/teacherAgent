from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pytest

from services.api.session_history_api_service import (
    SessionHistoryApiDeps,
    SessionHistoryApiError,
    student_history_session,
    student_history_sessions,
    student_session_view_state,
    teacher_history_session,
    teacher_history_sessions,
    teacher_session_view_state,
    update_student_session_view_state,
    update_teacher_session_view_state,
)


def _make_deps() -> tuple[SessionHistoryApiDeps, Dict[str, Any]]:
    state: Dict[str, Any] = {
        "student_states": {
            "stu-1": {"updated_at": "2026-02-12T10:00:00.000", "cursor": 1},
        },
        "teacher_states": {
            "tea-1": {"updated_at": "2026-02-12T10:00:00.000", "cursor": 2},
        },
        "saved_student": [],
        "saved_teacher": [],
        "student_path_calls": [],
        "teacher_path_calls": [],
        "message_calls": [],
    }

    def _paginate(items: List[Dict[str, Any]], cursor: int, limit: int) -> Tuple[List[Dict[str, Any]], Optional[int], int]:
        page = items[cursor : cursor + limit]
        next_cursor = cursor + limit if (cursor + limit) < len(items) else None
        return page, next_cursor, len(items)

    def _cmp(a: Optional[str], b: Optional[str]) -> int:
        aa = a or ""
        bb = b or ""
        return 1 if aa > bb else -1 if aa < bb else 0

    deps = SessionHistoryApiDeps(
        load_student_sessions_index=lambda sid: [
            {"session_id": f"{sid}-1"},
            {"session_id": f"{sid}-2"},
            {"session_id": f"{sid}-3"},
        ],
        load_teacher_sessions_index=lambda tid: [
            {"session_id": f"{tid}-1"},
            {"session_id": f"{tid}-2"},
        ],
        paginate_session_items=_paginate,
        load_student_session_view_state=lambda sid: dict(state["student_states"].get(sid) or {"updated_at": ""}),
        load_teacher_session_view_state=lambda tid: dict(state["teacher_states"].get(tid) or {"updated_at": ""}),
        normalize_session_view_state_payload=lambda payload: dict(payload),
        compare_iso_ts=_cmp,
        now_iso_millis=lambda: "2026-02-12T10:00:01.000",
        save_student_session_view_state=lambda sid, payload: state["saved_student"].append((sid, dict(payload)))
        or state["student_states"].__setitem__(sid, dict(payload)),
        save_teacher_session_view_state=lambda tid, payload: state["saved_teacher"].append((tid, dict(payload)))
        or state["teacher_states"].__setitem__(tid, dict(payload)),
        student_session_file=lambda sid, sess: state["student_path_calls"].append((sid, sess)) or f"student/{sid}/{sess}.jsonl",
        teacher_session_file=lambda tid, sess: state["teacher_path_calls"].append((tid, sess)) or f"teacher/{tid}/{sess}.jsonl",
        load_session_messages=lambda path, **kwargs: state["message_calls"].append((path, dict(kwargs)))
        or {"messages": [{"id": 1}, {"id": 2}], "next_cursor": 99},
        resolve_teacher_id=lambda tid: (tid or "tea-1").strip() or "tea-1",
    )
    return deps, state


def test_student_history_sessions_success_and_validation() -> None:
    deps, _ = _make_deps()

    with pytest.raises(SessionHistoryApiError, match="student_id is required"):
        student_history_sessions("", limit=2, cursor=0, deps=deps)

    out = student_history_sessions("  stu-1  ", limit=2, cursor=1, deps=deps)
    assert out["ok"] is True
    assert out["student_id"] == "stu-1"
    assert len(out["sessions"]) == 2
    assert out["total"] == 3


def test_student_session_view_state_success_and_validation() -> None:
    deps, _ = _make_deps()

    with pytest.raises(SessionHistoryApiError, match="student_id is required"):
        student_session_view_state("", deps=deps)

    out = student_session_view_state("stu-1", deps=deps)
    assert out["ok"] is True
    assert out["student_id"] == "stu-1"
    assert out["state"]["cursor"] == 1


def test_update_student_session_view_state_paths() -> None:
    deps, state = _make_deps()

    with pytest.raises(SessionHistoryApiError, match="student_id is required"):
        update_student_session_view_state({}, deps=deps)

    stale = update_student_session_view_state(
        {"student_id": "stu-1", "state": {"updated_at": "2026-02-12T09:59:59.000"}},
        deps=deps,
    )
    assert stale["stale"] is True
    assert state["saved_student"] == []

    fresh = update_student_session_view_state(
        {"student_id": "stu-new", "state": {"cursor": 10}},
        deps=deps,
    )
    assert fresh["stale"] is False
    assert fresh["student_id"] == "stu-new"
    assert fresh["state"]["updated_at"] == "2026-02-12T10:00:01.000"
    assert state["saved_student"]


def test_student_history_session_success_and_validation() -> None:
    deps, state = _make_deps()

    with pytest.raises(SessionHistoryApiError, match="student_id and session_id are required"):
        student_history_session("", "", cursor=0, limit=20, direction="older", deps=deps)

    out = student_history_session("stu-1", "sess-1", cursor=2, limit=10, direction="newer", deps=deps)
    assert out["ok"] is True
    assert out["messages"] == [{"id": 1}, {"id": 2}]
    assert out["next_cursor"] == 99
    assert state["student_path_calls"] == [("stu-1", "sess-1")]
    assert state["message_calls"][0][0] == "student/stu-1/sess-1.jsonl"


def test_teacher_history_sessions_and_view_state() -> None:
    deps, _ = _make_deps()

    sessions = teacher_history_sessions(None, limit=1, cursor=0, deps=deps)
    assert sessions["ok"] is True
    assert sessions["teacher_id"] == "tea-1"
    assert len(sessions["sessions"]) == 1

    state = teacher_session_view_state("  tea-1 ", deps=deps)
    assert state["ok"] is True
    assert state["teacher_id"] == "tea-1"
    assert state["state"]["cursor"] == 2


def test_update_teacher_session_view_state_paths() -> None:
    deps, state = _make_deps()

    stale = update_teacher_session_view_state(
        {"teacher_id": "tea-1", "state": {"updated_at": "2026-02-12T09:00:00.000"}},
        deps=deps,
    )
    assert stale["stale"] is True
    assert state["saved_teacher"] == []

    fresh = update_teacher_session_view_state(
        {"teacher_id": "tea-new", "state": {"cursor": 7}},
        deps=deps,
    )
    assert fresh["stale"] is False
    assert fresh["teacher_id"] == "tea-new"
    assert fresh["state"]["updated_at"] == "2026-02-12T10:00:01.000"
    assert state["saved_teacher"]


def test_teacher_history_session_success_and_validation() -> None:
    deps, state = _make_deps()

    with pytest.raises(SessionHistoryApiError, match="session_id is required"):
        teacher_history_session("", "tea-1", cursor=0, limit=20, direction="older", deps=deps)

    out = teacher_history_session("sess-9", None, cursor=1, limit=5, direction="older", deps=deps)
    assert out["ok"] is True
    assert out["teacher_id"] == "tea-1"
    assert out["messages"] == [{"id": 1}, {"id": 2}]
    assert out["next_cursor"] == 99
    assert state["teacher_path_calls"] == [("tea-1", "sess-9")]
    assert state["message_calls"][0][0] == "teacher/tea-1/sess-9.jsonl"
