from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

_log = logging.getLogger(__name__)

SCHEMA_V1 = 1
SCHEMA_V2 = 2
VISIBILITY_STATUSES = ("draft", "published", "archived", "orphan_draft", "retired_auto")
_VISIBILITY_SET = frozenset(VISIBILITY_STATUSES)

_CREATE_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS assignment_schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
)
"""

_CREATE_ASSIGNMENTS = """
CREATE TABLE IF NOT EXISTS assignments (
  assignment_id TEXT PRIMARY KEY,
  teacher_id TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  pack_id TEXT NOT NULL,
  date TEXT NOT NULL DEFAULT '',
  due_at TEXT NOT NULL DEFAULT '',
  visibility_status TEXT NOT NULL CHECK (
    visibility_status IN ('draft','published','archived','orphan_draft','retired_auto')
  ),
  archived_at TEXT,
  scope TEXT NOT NULL,
  class_name TEXT NOT NULL DEFAULT '',
  expected_students_json TEXT NOT NULL,
  expected_students_generated_at TEXT,
  completion_policy_json TEXT NOT NULL,
  meta_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""

_CREATE_PROGRESS = """
CREATE TABLE IF NOT EXISTS assignment_progress (
  assignment_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  submitted INTEGER NOT NULL,
  overdue INTEGER NOT NULL,
  official_score REAL,
  process_status TEXT NOT NULL DEFAULT 'none',
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (assignment_id, student_id)
)
"""

_CREATE_ATTEMPTS = """
CREATE TABLE IF NOT EXISTS student_submission_attempts (
  assignment_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  attempt_id TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  grading_report_json TEXT NOT NULL,
  files_json TEXT NOT NULL,
  PRIMARY KEY (assignment_id, student_id, attempt_id)
)
"""

_CREATE_GRADES = """
CREATE TABLE IF NOT EXISTS teacher_grades (
  assignment_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (assignment_id, student_id)
)
"""

_UPSERT_ASSIGNMENT = """
INSERT INTO assignments(
  assignment_id, teacher_id, subject_id, pack_id, date, due_at,
  visibility_status, archived_at, scope, class_name,
  expected_students_json, expected_students_generated_at,
  completion_policy_json, meta_json, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(assignment_id) DO UPDATE SET
  teacher_id=excluded.teacher_id,
  subject_id=excluded.subject_id,
  pack_id=excluded.pack_id,
  date=excluded.date,
  due_at=excluded.due_at,
  visibility_status=excluded.visibility_status,
  archived_at=excluded.archived_at,
  scope=excluded.scope,
  class_name=excluded.class_name,
  expected_students_json=excluded.expected_students_json,
  expected_students_generated_at=excluded.expected_students_generated_at,
  completion_policy_json=excluded.completion_policy_json,
  meta_json=excluded.meta_json,
  updated_at=excluded.updated_at
"""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _safe_id(token: str) -> bool:
    value = str(token or "").strip()
    if not value or value in {".", ".."}:
        return False
    if "/" in value or "\\" in value:
        return False
    return True


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def db_path_for(data_dir: Path) -> Path:
    return Path(data_dir).expanduser().resolve() / "auth" / "auth_registry.sqlite3"


def connect(data_dir: Path) -> sqlite3.Connection:
    path = db_path_for(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=3.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:  # policy: allowed-broad-except
        _log.warning("WAL journal mode not available for %s", path, exc_info=True)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_MIGRATIONS)
    conn.execute(_CREATE_ASSIGNMENTS)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignments_owner "
        "ON assignments(teacher_id, visibility_status, date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignments_subject "
        "ON assignments(subject_id, class_name)"
    )
    conn.execute(_CREATE_PROGRESS)
    conn.execute(_CREATE_ATTEMPTS)
    conn.execute(_CREATE_GRADES)


def has_migration(conn: sqlite3.Connection, version: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM assignment_schema_migrations WHERE version = ?",
        (int(version),),
    ).fetchone()
    return row is not None


def _record_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO assignment_schema_migrations(version, applied_at) VALUES (?, ?)",
        (int(version), _now_iso()),
    )


def ensure(conn: sqlite3.Connection, *, data_dir: Path, force_scan: bool = False) -> None:
    _create_tables(conn)
    _record_version(conn, SCHEMA_V1)
    v2_applied = has_migration(conn, SCHEMA_V2)
    # v2 is the one-shot JSON import; later boots must not rescan crash orphans.
    if force_scan or not v2_applied:
        import_json_legacy(conn, Path(data_dir))
        if not v2_applied:
            _record_version(conn, SCHEMA_V2)


def get_assignment(conn: sqlite3.Connection, assignment_id: str) -> Optional[sqlite3.Row]:
    aid = _text(assignment_id)
    if not aid:
        return None
    return conn.execute(
        "SELECT * FROM assignments WHERE assignment_id = ?",
        (aid,),
    ).fetchone()


def is_published(conn: sqlite3.Connection, assignment_id: str) -> bool:
    row = get_assignment(conn, assignment_id)
    return row is not None and _text(row["visibility_status"]) == "published"


def published_ids(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute(
        "SELECT assignment_id FROM assignments WHERE visibility_status = 'published'"
    ).fetchall()
    return {_text(row["assignment_id"]) for row in rows if _text(row["assignment_id"])}


def _visibility_from_meta(meta: Dict[str, Any], *, teacher_id: str) -> str:
    vis = _text(meta.get("visibility_status")).lower()
    if not teacher_id:
        return "orphan_draft"
    if vis in _VISIBILITY_SET:
        return vis
    return "draft"


def _row_values(meta: Dict[str, Any], *, now_iso: str) -> tuple:
    assignment_id = _text(meta.get("assignment_id"))
    teacher_id = _text(meta.get("teacher_id"))
    vis = _visibility_from_meta(meta, teacher_id=teacher_id)
    subject_id = _text(meta.get("subject_id"))
    pack_id = _text(meta.get("pack_id")) or subject_id
    expected = meta.get("expected_students")
    if not isinstance(expected, list):
        expected = []
    policy = meta.get("completion_policy")
    if not isinstance(policy, dict):
        policy = {}
    archived_at = meta.get("archived_at")
    archived_text = None if archived_at in (None, "") else str(archived_at)
    generated_at = _text(meta.get("expected_students_generated_at")) or None
    return (
        assignment_id,
        teacher_id,
        subject_id,
        pack_id,
        str(meta.get("date") or ""),
        str(meta.get("due_at") or ""),
        vis,
        archived_text,
        _text(meta.get("scope")) or "public",
        str(meta.get("class_name") or ""),
        _dumps(expected),
        generated_at,
        _dumps(policy),
        _dumps(meta),
        now_iso,
    )


def upsert_assignment(conn: sqlite3.Connection, meta: Dict[str, Any], *, now_iso: str) -> None:
    values = _row_values(meta, now_iso=now_iso)
    if not values[0]:
        return
    conn.execute(_UPSERT_ASSIGNMENT, values)


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _log.warning("skip unreadable json %s", path, exc_info=True)
        return None
    return payload if isinstance(payload, dict) else None


def _iter_assignment_meta(data_dir: Path) -> Iterable[tuple[str, Dict[str, Any]]]:
    root = Path(data_dir) / "assignments"
    if not root.is_dir():
        return
    for folder in root.iterdir():
        if not folder.is_dir() or not _safe_id(folder.name):
            continue
        meta_path = folder / "meta.json"
        if not meta_path.is_file():
            continue
        payload = _load_json_file(meta_path)
        if payload is None:
            continue
        assignment_id = _text(payload.get("assignment_id")) or folder.name
        payload["assignment_id"] = assignment_id
        yield assignment_id, payload


def _import_assignments(conn: sqlite3.Connection, data_dir: Path, now_iso: str) -> None:
    for _assignment_id, meta in _iter_assignment_meta(data_dir):
        upsert_assignment(conn, meta, now_iso=now_iso)


def _upsert_progress(
    conn: sqlite3.Connection,
    *,
    assignment_id: str,
    student: Dict[str, Any],
    now_iso: str,
) -> None:
    student_id = _text(student.get("student_id"))
    if not student_id:
        return
    official = student.get("official_score")
    try:
        official_score = None if official in (None, "") else float(official)
    except (TypeError, ValueError):
        official_score = None
    process_status = _text(student.get("process_archive_status") or student.get("process_status")) or "none"
    conn.execute(
        """
        INSERT INTO assignment_progress(
          assignment_id, student_id, submitted, overdue, official_score,
          process_status, payload_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(assignment_id, student_id) DO UPDATE SET
          submitted=excluded.submitted,
          overdue=excluded.overdue,
          official_score=excluded.official_score,
          process_status=excluded.process_status,
          payload_json=excluded.payload_json,
          updated_at=excluded.updated_at
        """,
        (
            assignment_id,
            student_id,
            1 if bool(student.get("submitted")) else 0,
            1 if bool(student.get("overdue")) else 0,
            official_score,
            process_status,
            _dumps(student),
            now_iso,
        ),
    )


def _import_progress(conn: sqlite3.Connection, data_dir: Path, now_iso: str) -> None:
    root = Path(data_dir) / "assignments"
    if not root.is_dir():
        return
    for folder in root.iterdir():
        if not folder.is_dir() or not _safe_id(folder.name):
            continue
        payload = _load_json_file(folder / "progress.json")
        if payload is None:
            continue
        students = payload.get("students")
        if not isinstance(students, list):
            continue
        assignment_id = _text(payload.get("assignment_id")) or folder.name
        for student in students:
            if isinstance(student, dict):
                _upsert_progress(
                    conn, assignment_id=assignment_id, student=student, now_iso=now_iso
                )


def _relative_files(attempt_dir: Path) -> list[str]:
    files: list[str] = []
    for path in sorted(attempt_dir.iterdir()):
        if path.is_file():
            files.append(path.name)
    return files


def _import_attempts(conn: sqlite3.Connection, data_dir: Path) -> None:
    root = Path(data_dir) / "student_submissions"
    if not root.is_dir():
        return
    for assignment_dir in root.iterdir():
        if not assignment_dir.is_dir() or not _safe_id(assignment_dir.name):
            continue
        for student_dir in assignment_dir.iterdir():
            if not student_dir.is_dir() or not _safe_id(student_dir.name):
                continue
            _import_student_attempts(conn, assignment_dir.name, student_dir)


def _import_student_attempts(
    conn: sqlite3.Connection, assignment_id: str, student_dir: Path
) -> None:
    student_id = student_dir.name
    for attempt_dir in sorted(student_dir.glob("submission_*")):
        if not attempt_dir.is_dir():
            continue
        report_path = attempt_dir / "grading_report.json"
        report = _load_json_file(report_path) or {}
        submitted_at = _text(report.get("submitted_at"))
        if not submitted_at:
            submitted_at = _now_iso()
        conn.execute(
            """
            INSERT INTO student_submission_attempts(
              assignment_id, student_id, attempt_id, submitted_at,
              grading_report_json, files_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(assignment_id, student_id, attempt_id) DO UPDATE SET
              submitted_at=excluded.submitted_at,
              grading_report_json=excluded.grading_report_json,
              files_json=excluded.files_json
            """,
            (
                assignment_id,
                student_id,
                attempt_dir.name,
                submitted_at,
                _dumps(report),
                _dumps(_relative_files(attempt_dir)),
            ),
        )


def _import_teacher_grades(conn: sqlite3.Connection, data_dir: Path, now_iso: str) -> None:
    root = Path(data_dir) / "student_submissions"
    if not root.is_dir():
        return
    for assignment_dir in root.iterdir():
        if not assignment_dir.is_dir() or not _safe_id(assignment_dir.name):
            continue
        for student_dir in assignment_dir.iterdir():
            if not student_dir.is_dir() or not _safe_id(student_dir.name):
                continue
            payload = _load_json_file(student_dir / "teacher_grade.json")
            if payload is None:
                continue
            conn.execute(
                """
                INSERT INTO teacher_grades(
                  assignment_id, student_id, payload_json, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(assignment_id, student_id) DO UPDATE SET
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (assignment_dir.name, student_dir.name, _dumps(payload), now_iso),
            )


def import_json_legacy(conn: sqlite3.Connection, data_dir: Path) -> None:
    now_iso = _now_iso()
    _import_assignments(conn, data_dir, now_iso)
    _import_progress(conn, data_dir, now_iso)
    _import_attempts(conn, data_dir)
    _import_teacher_grades(conn, data_dir, now_iso)


def load_published_ids(data_dir: Path) -> Set[str]:
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        return published_ids(conn)
    except sqlite3.Error:
        _log.warning("assignment sql published lookup failed", exc_info=True)
        return set()
    finally:
        conn.close()


def assignment_is_sql_published(data_dir: Path, assignment_id: str) -> bool:
    return assignment_sql_visibility(data_dir, assignment_id) == "published"


def visibility_map(conn: sqlite3.Connection) -> Dict[str, str]:
    rows = conn.execute(
        "SELECT assignment_id, visibility_status FROM assignments"
    ).fetchall()
    return {
        _text(row["assignment_id"]): _text(row["visibility_status"])
        for row in rows
        if _text(row["assignment_id"])
    }


def load_visibility_map(data_dir: Path) -> Dict[str, str]:
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        return visibility_map(conn)
    except sqlite3.Error:
        _log.warning("assignment sql visibility map failed", exc_info=True)
        return {}
    finally:
        conn.close()


def assignment_sql_visibility(data_dir: Path, assignment_id: str) -> str:
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        row = get_assignment(conn, assignment_id)
    except sqlite3.Error:
        _log.warning("assignment sql visibility check failed", exc_info=True)
        return ""
    finally:
        conn.close()
    return _text(row["visibility_status"]) if row is not None else ""


def sync_assignment_row(data_dir: Path, meta: Dict[str, Any]) -> None:
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        upsert_assignment(conn, meta, now_iso=_now_iso())
    finally:
        conn.close()
