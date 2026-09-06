from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from services.api.assignment.store import (
    SCHEMA_V2,
    connect,
    ensure,
    get_assignment,
    has_migration,
    published_ids,
    upsert_assignment,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "migrate_assignment_json_to_sqlite.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("migrate_assignment_json_to_sqlite_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_meta(data_dir: Path, assignment_id: str, meta: dict) -> None:
    folder = data_dir / "assignments" / assignment_id
    folder.mkdir(parents=True, exist_ok=True)
    payload = {"assignment_id": assignment_id, **meta}
    (folder / "meta.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _published(**overrides: object) -> dict:
    payload: dict = {
        "teacher_id": "t_zhang",
        "subject_id": "physics",
        "pack_id": "physics",
        "visibility_status": "published",
        "scope": "public",
        "class_name": "",
        "expected_students": ["S1"],
        "date": "2026-08-28",
        "completion_policy": {"version": 2},
    }
    payload.update(overrides)
    return payload


def test_ensure_creates_tables_and_wal(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "assignments" in names
        assert "assignment_progress" in names
        assert "student_submission_attempts" in names
        assert "teacher_grades" in names
        assert "assignment_schema_migrations" in names
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "wal"
        assert has_migration(conn, SCHEMA_V2) is True
    finally:
        conn.close()


def test_ensure_is_one_shot_and_does_not_rescan_json(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        assert has_migration(conn, SCHEMA_V2) is True
        _write_meta(data_dir, "HW_CRASH", _published())
        ensure(conn, data_dir=data_dir)
        assert get_assignment(conn, "HW_CRASH") is None
        assert "HW_CRASH" not in published_ids(conn)
    finally:
        conn.close()


def test_cli_apply_is_noop_after_v2(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
    finally:
        conn.close()
    _write_meta(data_dir, "HW_JSON_ONLY", _published())
    script = _load_script()
    code = script.main(["--apply", "--data-dir", str(data_dir)])
    assert code == 0
    conn = connect(data_dir)
    try:
        assert get_assignment(conn, "HW_JSON_ONLY") is None
    finally:
        conn.close()


def test_orphan_teacher_id_is_allowed_without_teacher_auth_fk(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        upsert_assignment(
            conn,
            {
                "assignment_id": "HW_ORPHAN",
                "teacher_id": "missing_teacher",
                "subject_id": "physics",
                "pack_id": "physics",
                "visibility_status": "orphan_draft",
                "scope": "public",
                "expected_students": [],
                "completion_policy": {},
            },
            now_iso="2026-08-28T00:00:00+00:00",
        )
        row = get_assignment(conn, "HW_ORPHAN")
        assert row is not None
        assert row["teacher_id"] == "missing_teacher"
        assert row["visibility_status"] == "orphan_draft"
    finally:
        conn.close()


def test_visibility_status_check_rejects_unknown(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                (
                    "INSERT INTO assignments("
                    "assignment_id, teacher_id, subject_id, pack_id, date, due_at, "
                    "visibility_status, archived_at, scope, class_name, "
                    "expected_students_json, expected_students_generated_at, "
                    "completion_policy_json, meta_json, updated_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    "HW_BAD",
                    "t_zhang",
                    "physics",
                    "physics",
                    "",
                    "",
                    "visible",
                    None,
                    "public",
                    "",
                    "[]",
                    None,
                    "{}",
                    "{}",
                    "2026-08-28T00:00:00+00:00",
                ),
            )
    finally:
        conn.close()


def test_migrate_imports_progress_and_submissions_without_deleting_json(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _write_meta(data_dir, "HW_1", _published())
    progress_path = data_dir / "assignments" / "HW_1" / "progress.json"
    progress_path.write_text(
        json.dumps(
            {
                "students": [
                    {
                        "student_id": "S1",
                        "submitted": True,
                        "overdue": False,
                        "official_score": 9.5,
                        "process_archive_status": "frozen",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    attempt_dir = data_dir / "student_submissions" / "HW_1" / "S1" / "submission_1"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "page1.pdf").write_bytes(b"%PDF")
    (attempt_dir / "grading_report.json").write_text(
        json.dumps({"graded_total": 1, "score_earned": 9.5}),
        encoding="utf-8",
    )
    grade_path = data_dir / "student_submissions" / "HW_1" / "S1" / "teacher_grade.json"
    grade_path.write_text(
        json.dumps({"schema": "teacher_grade/v1", "override_score_earned": 10}),
        encoding="utf-8",
    )
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        progress = conn.execute(
            "SELECT submitted, official_score, process_status FROM assignment_progress "
            "WHERE assignment_id = ? AND student_id = ?",
            ("HW_1", "S1"),
        ).fetchone()
        assert progress is not None
        assert int(progress["submitted"]) == 1
        assert float(progress["official_score"]) == 9.5
        attempt = conn.execute(
            "SELECT attempt_id FROM student_submission_attempts "
            "WHERE assignment_id = ? AND student_id = ?",
            ("HW_1", "S1"),
        ).fetchone()
        assert attempt is not None
        grade = conn.execute(
            "SELECT payload_json FROM teacher_grades WHERE assignment_id = ? AND student_id = ?",
            ("HW_1", "S1"),
        ).fetchone()
        assert grade is not None
    finally:
        conn.close()
    assert (data_dir / "assignments" / "HW_1" / "meta.json").exists()
    assert progress_path.exists()
    assert grade_path.exists()
