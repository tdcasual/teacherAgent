"""Tests for services.api.assignment_progress_service."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

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
        today_iso=lambda: "2026-01-15",
        now_iso=lambda: "2026-01-15T00:00:00Z",
    )
    defaults.update(overrides)
    return AssignmentProgressDeps(**defaults)


def _setup_assignment(tmp_path: Path, aid: str = "hw1",
                      students: List[str] | None = None,
                      due_at: str = "") -> Dict[str, Any]:
    folder = tmp_path / "assignments" / aid
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "assignment_id": aid,
        "teacher_id": "t_zhang",
        "subject_id": "physics",
        "visibility_status": "published",
        "expected_students": students or [],
        "due_at": due_at,
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
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
            today_iso=lambda: "2026-01-15",
        )
        result = compute_assignment_progress("hw1", deps=deps)
        assert result["counts"]["overdue"] == 1
        assert result["students"][0]["overdue"] is True

    def test_completed_is_submitted_even_without_discussion(self, tmp_path: Path):
        meta = _setup_assignment(tmp_path, "hw1", ["s1", "s2"])
        meta["completion_policy"] = {
            "requires_discussion": True,
            "requires_submission": True,
            "min_graded_total": 1,
            "version": 1,
        }
        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            list_all_student_profiles=lambda: [
                {"student_id": "s1"},
                {"student_id": "s2"},
            ],
            session_discussion_pass=lambda s, _a: {"pass": True} if s == "s2" else {},
            list_submission_attempts=lambda _a, s: (
                [{"graded_total": 1, "score_earned": 3}] if s == "s1" else []
            ),
        )
        result = compute_assignment_progress("hw1", deps=deps)
        by_id = {row["student_id"]: row for row in result["students"]}
        assert by_id["s1"]["complete"] is True
        assert by_id["s1"]["submitted"] is True
        assert by_id["s2"]["complete"] is False
        assert by_id["s2"]["discussion"]["pass"] is True
        assert result["counts"]["completed"] == 1

    def test_overdue_is_calendar_day_and_ignores_discussion(self, tmp_path: Path):
        meta = _setup_assignment(tmp_path, "hw1", ["s1", "s2", "s3"], due_at="2026-08-30T00:00:00")
        meta["completion_policy"] = {"requires_discussion": True, "requires_submission": True}
        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            list_all_student_profiles=lambda: [
                {"student_id": "s1"},
                {"student_id": "s2"},
                {"student_id": "s3"},
            ],
            session_discussion_pass=lambda s, _a: {"pass": True} if s != "s1" else {},
            list_submission_attempts=lambda _a, s: (
                [{"graded_total": 1, "score_earned": 8}] if s == "s1" else []
            ),
            today_iso=lambda: "2026-08-30",
        )
        same_day = compute_assignment_progress("hw1", deps=deps)
        assert same_day["counts"]["overdue"] == 0
        by_id = {row["student_id"]: row for row in same_day["students"]}
        assert by_id["s1"]["overdue"] is False
        assert by_id["s2"]["overdue"] is False

        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            list_all_student_profiles=lambda: [
                {"student_id": "s1"},
                {"student_id": "s2"},
                {"student_id": "s3"},
            ],
            session_discussion_pass=lambda s, _a: {"pass": True} if s != "s1" else {},
            list_submission_attempts=lambda _a, s: (
                [{"graded_total": 1, "score_earned": 8}] if s == "s1" else []
            ),
            today_iso=lambda: "2026-08-31",
        )
        next_day = compute_assignment_progress("hw1", deps=deps)
        by_id = {row["student_id"]: row for row in next_day["students"]}
        assert by_id["s1"]["overdue"] is False
        assert by_id["s2"]["overdue"] is True
        assert by_id["s2"]["discussion"]["pass"] is True
        assert next_day["counts"]["overdue"] == 2

    def test_default_policy_v2_does_not_require_discussion(self, tmp_path: Path):
        meta = _setup_assignment(tmp_path, "hw1", ["s1"])
        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            list_all_student_profiles=lambda: [{"student_id": "s1"}],
            session_discussion_pass=lambda _s, _a: {},
            list_submission_attempts=lambda _a, _s: [{"graded_total": 1, "score_earned": 4}],
        )
        result = compute_assignment_progress("hw1", deps=deps)
        student = result["students"][0]
        assert student["complete"] is True
        assert student["completion"]["policy"]["requires_discussion"] is False
        assert student["completion"]["policy"]["version"] == 2
        assert student["process"]["status"] == "none"

    def test_official_score_prefers_teacher_override(self, tmp_path: Path):
        import json

        meta = _setup_assignment(tmp_path, "hw1", ["s1"])
        grade_path = tmp_path / "student_submissions" / "hw1" / "s1" / "teacher_grade.json"
        grade_path.parent.mkdir(parents=True, exist_ok=True)
        grade_path.write_text(
            json.dumps(
                {
                    "schema": "teacher_grade/v1",
                    "override_score_earned": 11.5,
                    "comment": "单位漏写",
                    "adopted_coach_excerpts": [],
                }
            ),
            encoding="utf-8",
        )
        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            list_all_student_profiles=lambda: [{"student_id": "s1"}],
            list_submission_attempts=lambda _a, _s: [{"graded_total": 2, "score_earned": 8}],
        )
        result = compute_assignment_progress("hw1", deps=deps)
        student = result["students"][0]
        assert student["official_score"] == 11.5
        assert student["result"]["official_score"] == 11.5
        assert student["result"]["attempts"] == 1

        grade_path.write_text(
            json.dumps(
                {
                    "schema": "teacher_grade/v1",
                    "override_score_earned": None,
                    "comment": "单位漏写",
                    "adopted_coach_excerpts": [],
                }
            ),
            encoding="utf-8",
        )
        restored = compute_assignment_progress("hw1", deps=deps)
        assert restored["students"][0]["official_score"] == 8.0

    def test_atomic_write_failure_logged(self, tmp_path: Path, caplog):
        meta = _setup_assignment(tmp_path, "hw1", [])
        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            atomic_write_json=lambda _p, _d: (_ for _ in ()).throw(OSError("disk full")),
        )
        with caplog.at_level(logging.WARNING):
            result = compute_assignment_progress("hw1", deps=deps)
        assert result["ok"] is False
        assert result.get("error") == "assignment_persist_failed"
        assert result.get("status") == 500
        assert "failed to persist progress" in caplog.text

    def test_practice_dirs_do_not_change_submitted_count(self, tmp_path: Path):
        meta = _setup_assignment(tmp_path, "hw1", ["s1"])
        practice = tmp_path / "student_submissions" / "hw1" / "s1" / "practice_ab12cd"
        practice.mkdir(parents=True, exist_ok=True)
        (practice / "meta.json").write_text(
            json.dumps({"practice_id": "practice_ab12cd", "status": "submitted"}),
            encoding="utf-8",
        )
        (practice / "grading_report.json").write_text(
            json.dumps({"graded_total": 3, "correct": 3, "items": []}),
            encoding="utf-8",
        )
        deps = _make_deps(
            tmp_path,
            load_assignment_meta=lambda _f: meta,
            list_all_student_profiles=lambda: [{"student_id": "s1"}],
            list_submission_attempts=lambda _a, _s: [],
        )
        result = compute_assignment_progress("hw1", deps=deps)
        assert result["counts"]["submitted"] == 0
        student = result["students"][0]
        assert student["submitted"] is False
        assert student["practice"]["assigned"] == 1
        assert student["practice"]["submitted"] == 1
        assert student["practice"]["open"] == 0


def _progress_sql_rows(tmp_path: Path, assignment_id: str):
    from services.api.assignment.store import connect, ensure

    conn = connect(tmp_path)
    try:
        ensure(conn, data_dir=tmp_path)
        return list(
            conn.execute(
                "SELECT student_id, submitted, overdue, official_score, process_status, payload_json "
                "FROM assignment_progress WHERE assignment_id = ? ORDER BY student_id",
                (assignment_id,),
            ).fetchall()
        )
    finally:
        conn.close()


def test_compute_writes_sql_progress_rows(tmp_path: Path):
    from services.api.fs_atomic import atomic_write_json as real_atomic_write_json

    meta = _setup_assignment(tmp_path, "hw1", ["s1", "s2"])
    deps = _make_deps(
        tmp_path,
        load_assignment_meta=lambda _f: meta,
        list_all_student_profiles=lambda: [
            {"student_id": "s1", "student_name": "Alice", "class_name": "A"},
            {"student_id": "s2", "student_name": "Bob", "class_name": "A"},
        ],
        list_submission_attempts=lambda _a, s: (
            [{"graded_total": 1, "score_earned": 9}] if s == "s1" else []
        ),
        atomic_write_json=real_atomic_write_json,
    )
    result = compute_assignment_progress("hw1", deps=deps)
    assert result["ok"] is True
    rows = _progress_sql_rows(tmp_path, "hw1")
    assert len(rows) == 2
    by_id = {row["student_id"]: row for row in rows}
    assert int(by_id["s1"]["submitted"]) == 1
    assert int(by_id["s2"]["submitted"]) == 0
    assert float(by_id["s1"]["official_score"]) == 9.0
    payload = json.loads(by_id["s1"]["payload_json"])
    assert payload["student_id"] == "s1"
    assert payload["submitted"] is True

    slim = compute_assignment_progress("hw1", deps=deps, include_students=False)
    assert slim["ok"] is True
    assert slim["students"] == []
    slim_rows = _progress_sql_rows(tmp_path, "hw1")
    slim_by_id = {row["student_id"]: row for row in slim_rows}
    assert json.loads(slim_by_id["s1"]["payload_json"]) == {}
    assert json.loads(slim_by_id["s2"]["payload_json"]) == {}
    assert int(slim_by_id["s1"]["submitted"]) == 1


def test_sql_row_without_folder_is_not_404(tmp_path: Path):
    from services.api.assignment.store import connect, ensure, upsert_assignment
    from services.api.fs_atomic import atomic_write_json as real_atomic_write_json

    conn = connect(tmp_path)
    try:
        ensure(conn, data_dir=tmp_path)
        upsert_assignment(
            conn,
            {
                "assignment_id": "ghost",
                "teacher_id": "t_zhang",
                "subject_id": "physics",
                "visibility_status": "published",
                "scope": "public",
                "expected_students": ["s1"],
                "completion_policy": {},
            },
            now_iso="2026-01-15T00:00:00+00:00",
        )
    finally:
        conn.close()
    assert not (tmp_path / "assignments" / "ghost").exists()
    deps = _make_deps(tmp_path, atomic_write_json=real_atomic_write_json)
    result = compute_assignment_progress("ghost", deps=deps)
    assert result.get("error") != "assignment_not_found"
    assert result.get("ok") is True
    assert result.get("assignment_id") == "ghost"
    assert result.get("counts", {}).get("expected") == 1
    assert not (tmp_path / "assignments" / "ghost").exists()


def test_compute_json_write_failure_rolls_back_sql(tmp_path: Path):
    meta = _setup_assignment(tmp_path, "hw1", ["s1"])
    deps = _make_deps(
        tmp_path,
        load_assignment_meta=lambda _f: meta,
        list_all_student_profiles=lambda: [{"student_id": "s1"}],
        list_submission_attempts=lambda _a, _s: [{"graded_total": 1, "score_earned": 4}],
        atomic_write_json=lambda _p, _d: (_ for _ in ()).throw(OSError("disk full")),
    )
    result = compute_assignment_progress("hw1", deps=deps)
    assert result.get("ok") is False
    assert result.get("error") == "assignment_persist_failed"
    assert result.get("status") == 500
    rows = _progress_sql_rows(tmp_path, "hw1")
    assert rows == []
