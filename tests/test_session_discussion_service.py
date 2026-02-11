"""Tests for session_discussion_service.session_discussion_pass."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.api.session_discussion_service import (
    SessionDiscussionDeps,
    session_discussion_pass,
)

MARKER = "[[DISCUSSION_COMPLETE]]"


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for obj in lines:
            f.write(json.dumps(obj) + "\n")


def _make_deps(tmp_path: Path, marker: str = MARKER, index: list | None = None) -> SessionDiscussionDeps:
    return SessionDiscussionDeps(
        marker=marker,
        load_student_sessions_index=lambda _sid: index or [],
        student_session_file=lambda _sid, sess_id: tmp_path / f"{sess_id}.jsonl",
    )


# ── 1. Not started ──────────────────────────────────────────────────

def test_not_started_no_file(tmp_path):
    deps = _make_deps(tmp_path)
    res = session_discussion_pass("s1", "a1", deps=deps)
    assert res["status"] == "not_started"
    assert res["pass"] is False
    assert res["message_count"] == 0


# ── 2. In progress ──────────────────────────────────────────────────

def test_in_progress_no_marker(tmp_path):
    _write_jsonl(tmp_path / "a1.jsonl", [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ])
    res = session_discussion_pass("s1", "a1", deps=_make_deps(tmp_path))
    assert res["status"] == "in_progress"
    assert res["pass"] is False
    assert res["message_count"] == 2


# ── 3. Pass ──────────────────────────────────────────────────────────

def test_pass_assistant_marker(tmp_path):
    _write_jsonl(tmp_path / "a1.jsonl", [
        {"role": "user", "content": "explain gravity"},
        {"role": "assistant", "content": f"Great job! {MARKER}"},
    ])
    res = session_discussion_pass("s1", "a1", deps=_make_deps(tmp_path))
    assert res["status"] == "pass"
    assert res["pass"] is True
    assert res["session_id"] == "a1"


# ── 4. User message with marker NOT trusted ──────────────────────────

def test_user_marker_not_trusted(tmp_path):
    _write_jsonl(tmp_path / "a1.jsonl", [
        {"role": "user", "content": f"I say {MARKER}"},
        {"role": "assistant", "content": "nice try"},
    ])
    res = session_discussion_pass("s1", "a1", deps=_make_deps(tmp_path))
    assert res["status"] == "in_progress"
    assert res["pass"] is False


# ── 5. Multiple sessions — picks the passing one ─────────────────────

def test_multiple_sessions_picks_pass(tmp_path):
    _write_jsonl(tmp_path / "a1.jsonl", [
        {"role": "user", "content": "hi"},
    ])
    _write_jsonl(tmp_path / "sess2.jsonl", [
        {"role": "assistant", "content": f"done {MARKER}"},
    ])
    index = [{"assignment_id": "a1", "session_id": "sess2"}]
    deps = _make_deps(tmp_path, index=index)
    res = session_discussion_pass("s1", "a1", deps=deps)
    assert res["pass"] is True
    assert res["session_id"] == "sess2"


# ── 6. Both passing — picks more messages ────────────────────────────

def test_both_passing_picks_more_messages(tmp_path):
    _write_jsonl(tmp_path / "a1.jsonl", [
        {"role": "assistant", "content": MARKER},
    ])
    _write_jsonl(tmp_path / "sess2.jsonl", [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": f"a {MARKER}"},
        {"role": "user", "content": "thanks"},
    ])
    index = [{"assignment_id": "a1", "session_id": "sess2"}]
    deps = _make_deps(tmp_path, index=index)
    res = session_discussion_pass("s1", "a1", deps=deps)
    assert res["session_id"] == "sess2"
    assert res["message_count"] == 3


# ── 7. Session index fallback ────────────────────────────────────────

def test_index_fallback_when_primary_missing(tmp_path):
    _write_jsonl(tmp_path / "alt.jsonl", [
        {"role": "assistant", "content": f"ok {MARKER}"},
    ])
    index = [{"assignment_id": "a1", "session_id": "alt"}]
    deps = _make_deps(tmp_path, index=index)
    res = session_discussion_pass("s1", "a1", deps=deps)
    assert res["pass"] is True
    assert res["session_id"] == "alt"


# ── 8. Corrupt JSONL lines skipped ──────────────────────────────────

def test_corrupt_jsonl_skipped(tmp_path):
    p = tmp_path / "a1.jsonl"
    p.write_text(
        '{"role":"assistant","content":"hi"}\n'
        "NOT_JSON\n"
        f'{{"role":"assistant","content":"{MARKER}"}}\n'
    )
    res = session_discussion_pass("s1", "a1", deps=_make_deps(tmp_path))
    assert res["pass"] is True
    assert res["message_count"] == 2  # corrupt line skipped


# ── 9. Empty marker never triggers pass ──────────────────────────────

def test_empty_marker_never_passes(tmp_path):
    _write_jsonl(tmp_path / "a1.jsonl", [
        {"role": "assistant", "content": "anything here"},
    ])
    deps = _make_deps(tmp_path, marker="")
    res = session_discussion_pass("s1", "a1", deps=deps)
    assert res["status"] == "in_progress"
    assert res["pass"] is False
