"""Tests for services.api.assignment_progress_service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from services.api.assignment_progress_service import (
    AssignmentProgressDeps,
    _resolve_assignment_dir,
    compute_assignment_progress,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_deps(tmp_path: Path, **overrides: Any) -> AssignmentProgressDeps:
    defaults = dict(
        data_dir=tmp_path,
        load_assignment_meta=lambda _f: {},
        postprocess_assignment_meta=lambda _aid: None,
        normalize_due_at=lambda v: v or "",
        list_all_student_profiles=lambda: [],
        session_discussion_pass=lambda _s, _a: {},
        list_submission_attempts=lambda _a, _s: [],
        best_submission_attempt=lambda atts: atts[0] if atts else None,
        resolve_assignment_date=lambda _m, _f: "2026-01-01",
        atomic_write_json=lambda _p, _d: None,
        time_time=lambda: 1_700_000_000.0,
        now_iso=lambda: "2026-01-15T00:00:00Z",
    )
    defaults.update(overrides)
    return AssignmentProgressDeps(**defaults)


def _setup_assignment(tmp_path: Path, aid: str = "hw1",
                      students: List[str] | None = None,
                      due_at: str = "") -> Dict[str, Any]:
    folder = tmp_path / "assignments" / aid
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"assignment_id": aid, "expected_students": students or [], "due_at": due_at}
    return meta


# ---------------------------------------------------------------------------
# _resolve_assignment_dir
# ---------------------------------------------------------------------------

class TestResolveAssignmentDir:
    def test_valid_id(self, tmp_path: Path):
        result = _resolve_assignment_dir(tmp_path, "hw1")
        assert result == (tmp_path / "assignments" / "hw1").resolve()

    def test_empty_id_returns_none(self, tmp_path: Path):
        assert _resolve_assignment_dir(tmp_path, "") is None
        assert _resolve_assignment_dir(tmp_path, "   ") is None

    def test_path_traversal_returns_none(self, tmp_path: Path):
        assert _resolve_assignment_dir(tmp_path, "../etc") is None
        assert _resolve_assignment_dir(tmp_path, "../../passwd") is None


# ---------------------------------------------------------------------------
# compute_assignment_progress
# ---------------------------------------------------------------------------

class TestComputeAssignmentProgress:
    def test_assignment_not_found(self, tmp_path: Path):
        deps = _make_deps(tmp_path)
        result = compute_assignment_progress("missing", deps=deps)
        assert result == {"ok": False, "error": "assignment_not_found",
                          "assignment_id": "missing"}

    def test_basic_progress_two_students(self, tmp_path: Path):
        meta = _setup_assignment(tmp_path, "hw1", ["s1", "s2"])

        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            list_all_student_profiles=lambda: [
                {"student_id": "s1", "student_name": "Alice", "class_name": "A"},
                {"student_id": "s2", "student_name": "Bob", "class_name": "A"},
            ],
            session_discussion_pass=lambda s, _a: {"pass": True} if s == "s1" else {},
            list_submission_attempts=lambda _a, s: [{"score": 90}] if s == "s1" else [],
        )
        result = compute_assignment_progress("hw1", deps=deps)
        assert result["ok"] is True
        assert result["counts"]["completed"] == 1
        assert result["counts"]["submitted"] == 1
        assert result["counts"]["discussion_pass"] == 1
        assert len(result["students"]) == 2

    def test_include_students_false(self, tmp_path: Path):
        meta = _setup_assignment(tmp_path, "hw1", ["s1"])
        deps = _make_deps(tmp_path, load_assignment_meta=lambda _f: meta,
                          list_all_student_profiles=lambda: [{"student_id": "s1"}],
                          session_discussion_pass=lambda _s, _a: {})
        result = compute_assignment_progress("hw1", deps=deps, include_students=False)
        assert result["ok"] is True
        assert result["students"] == []

    def test_overdue_detection(self, tmp_path: Path):
        past_due = "2025-06-01T00:00:00Z"
        meta = _setup_assignment(tmp_path, "hw1", ["s1"], due_at=past_due)

        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            normalize_due_at=lambda v: v or "",
            list_all_student_profiles=lambda: [{"student_id": "s1"}],
            session_discussion_pass=lambda _s, _a: {},
            list_submission_attempts=lambda _a, _s: [],
            time_time=lambda: 1_800_000_000.0,  # well past due
        )
        result = compute_assignment_progress("hw1", deps=deps)
        assert result["counts"]["overdue"] == 1
        assert result["students"][0]["overdue"] is True

    def test_atomic_write_failure_logged(self, tmp_path: Path, caplog):
        meta = _setup_assignment(tmp_path, "hw1", [])
        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            atomic_write_json=lambda _p, _d: (_ for _ in ()).throw(OSError("disk full")),
        )
        with caplog.at_level(logging.WARNING):
            result = compute_assignment_progress("hw1", deps=deps)
        assert result["ok"] is True
        assert "failed to write progress.json" in caplog.text
