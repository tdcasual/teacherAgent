from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

from ..config import APP_ROOT
from ..core_utils import normalize

_HARD_SEED_SUBJECTS = (
    ("generic", "通用", "generic"),
    ("physics", "物理", "physics"),
)

_CONFLICT_ERRORS = frozenset({"class_already_owned", "enrollments_remain", "subject_exists"})


class ExpectedStudentsError(Exception):
    def __init__(self, error: str):
        super().__init__(error)
        self.error = str(error or "roster_required")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return str(value or "").strip()


@contextmanager
def _borrow_conn(
    store: Any, conn: Optional[sqlite3.Connection] = None
) -> Iterator[sqlite3.Connection]:
    if conn is not None:
        yield conn
        return
    owned = store._connect()
    try:
        yield owned
    finally:
        owned.close()


def _fail(error: str, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": False, "error": error}
    payload.update(extra)
    return payload


def _ok(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    payload.update(extra)
    return payload


def _default_packs_root() -> Path:
    return Path(APP_ROOT) / "packs" / "subjects"


def ensure_roster_tables(store: Any) -> None:
    with store._connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teacher_roster (
                teacher_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                PRIMARY KEY (teacher_id, subject_id, class_name)
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS teacher_roster_one_owner
            ON teacher_roster (subject_id, class_name)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_enrollments (
                student_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                teacher_id TEXT NOT NULL,
                PRIMARY KEY (student_id, subject_id, class_name)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_teacher_roster_teacher "
            "ON teacher_roster(teacher_id, subject_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_enrollments_class "
            "ON student_enrollments(subject_id, class_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_enrollments_teacher "
            "ON student_enrollments(teacher_id, subject_id)"
        )
    seed_subjects(store)


def seed_subjects(store: Any, *, packs_root: Optional[Path] = None) -> Dict[str, Any]:
    created_at = _now_iso()
    with store._connect() as conn:
        _hard_seed_subjects(conn, created_at=created_at)
        synced = _pack_sync_subjects(conn, packs_root=packs_root, created_at=created_at)
    items = list_subjects(store).get("items") or []
    return _ok(count=len(items), synced=synced, items=items)


def _hard_seed_subjects(conn: sqlite3.Connection, *, created_at: str) -> None:
    for subject_id, display_name, pack_id in _HARD_SEED_SUBJECTS:
        conn.execute(
            (
                "INSERT OR IGNORE INTO subjects(subject_id, display_name, pack_id, created_at) "
                "VALUES (?, ?, ?, ?)"
            ),
            (subject_id, display_name, pack_id, created_at),
        )


def _pack_sync_subjects(
    conn: sqlite3.Connection, *, packs_root: Optional[Path], created_at: str
) -> int:
    root = Path(packs_root) if packs_root is not None else _default_packs_root()
    if not root.exists():
        return 0
    synced = 0
    for pack_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if _upsert_pack_subject(conn, pack_dir=pack_dir, created_at=created_at):
            synced += 1
    return synced


def _load_pack_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _upsert_pack_subject(conn: sqlite3.Connection, *, pack_dir: Path, created_at: str) -> bool:
    yaml_path = pack_dir / "pack.yaml"
    if not yaml_path.is_file():
        return False
    data = _load_pack_yaml(yaml_path)
    subject_id = _text(data.get("id") or data.get("subject_id") or pack_dir.name)
    if not subject_id:
        return False
    pack_id = _text(data.get("pack_id") or subject_id)
    display_name = _text(data.get("display_name") or data.get("name") or subject_id)
    existing = conn.execute(
        "SELECT subject_id, display_name, pack_id FROM subjects WHERE subject_id = ?",
        (subject_id,),
    ).fetchone()
    if existing is None:
        conn.execute(
            (
                "INSERT INTO subjects(subject_id, display_name, pack_id, created_at) "
                "VALUES (?, ?, ?, ?)"
            ),
            (subject_id, display_name, pack_id, created_at),
        )
        return True
    if _text(existing["pack_id"]) != pack_id:
        conn.execute(
            "UPDATE subjects SET pack_id = ? WHERE subject_id = ?",
            (pack_id, subject_id),
        )
        return True
    return False


def list_subjects(store: Any) -> Dict[str, Any]:
    with store._connect() as conn:
        rows = conn.execute(
            "SELECT subject_id, display_name, pack_id, created_at FROM subjects "
            "ORDER BY subject_id"
        ).fetchall()
    items = [
        {
            "subject_id": _text(row["subject_id"]),
            "display_name": _text(row["display_name"]),
            "pack_id": _text(row["pack_id"]),
            "created_at": _text(row["created_at"]),
        }
        for row in rows
    ]
    return _ok(count=len(items), items=items)


def add_subject(
    store: Any,
    *,
    subject_id: str,
    display_name: str,
    pack_id: str = "",
) -> Dict[str, Any]:
    sid = _text(subject_id)
    name = _text(display_name)
    pack = _text(pack_id) or "generic"
    if not sid:
        return _fail("missing_subject_id")
    if not name:
        return _fail("missing_display_name")
    created_at = _now_iso()
    with store._connect() as conn:
        existing = conn.execute(
            "SELECT subject_id, display_name, pack_id, created_at FROM subjects WHERE subject_id = ?",
            (sid,),
        ).fetchone()
        if existing is not None:
            return _ok(
                created=False,
                subject={
                    "subject_id": _text(existing["subject_id"]),
                    "display_name": _text(existing["display_name"]),
                    "pack_id": _text(existing["pack_id"]),
                    "created_at": _text(existing["created_at"]),
                },
            )
        conn.execute(
            (
                "INSERT INTO subjects(subject_id, display_name, pack_id, created_at) "
                "VALUES (?, ?, ?, ?)"
            ),
            (sid, name, pack, created_at),
        )
    return _ok(
        created=True,
        subject={
            "subject_id": sid,
            "display_name": name,
            "pack_id": pack,
            "created_at": created_at,
        },
    )


def _subject_exists(conn: sqlite3.Connection, subject_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM subjects WHERE subject_id = ?",
        (subject_id,),
    ).fetchone()
    return row is not None


def _teacher_exists(conn: sqlite3.Connection, teacher_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM teacher_auth WHERE teacher_id = ?",
        (teacher_id,),
    ).fetchone()
    return row is not None


def _student_exists(conn: sqlite3.Connection, student_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM student_auth WHERE student_id = ?",
        (student_id,),
    ).fetchone()
    return row is not None


def _roster_owner(conn: sqlite3.Connection, *, subject_id: str, class_name: str) -> Optional[str]:
    row = conn.execute(
        "SELECT teacher_id FROM teacher_roster WHERE subject_id = ? AND class_name = ?",
        (subject_id, class_name),
    ).fetchone()
    if row is None:
        return None
    return _text(row["teacher_id"]) or None


def _count_class_auth_students(conn: sqlite3.Connection, class_name: str) -> int:
    class_norm = normalize(class_name)
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM student_auth WHERE class_name = ? OR class_norm = ?",
        (class_name, class_norm),
    ).fetchone()
    return int(row["n"] if row is not None else 0)


def _count_enrollments(conn: sqlite3.Connection, *, subject_id: str, class_name: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM student_enrollments WHERE subject_id = ? AND class_name = ?",
        (subject_id, class_name),
    ).fetchone()
    return int(row["n"] if row is not None else 0)


def add_roster(
    store: Any,
    *,
    teacher_id: str,
    subject_id: str,
    class_name: str,
    allow_empty: bool = True,
) -> Dict[str, Any]:
    tid = _text(teacher_id)
    sid = _text(subject_id)
    class_text = _text(class_name)
    if not tid:
        return _fail("missing_teacher_id")
    if not sid:
        return _fail("missing_subject_id")
    if not class_text:
        return _fail("missing_class_name")
    with store._connect() as conn:
        if not _teacher_exists(conn, tid):
            return _fail("teacher_not_found")
        if not _subject_exists(conn, sid):
            return _fail("subject_not_found")
        owner = _roster_owner(conn, subject_id=sid, class_name=class_text)
        if owner and owner != tid:
            return _fail("class_already_owned")
        empty_count = _count_class_auth_students(conn, class_text)
        warning = "empty_class" if empty_count == 0 else ""
        if empty_count == 0 and not allow_empty:
            return _fail("empty_class", warning="empty_class")
        if owner == tid:
            return _ok(
                teacher_id=tid,
                subject_id=sid,
                class_name=class_text,
                warning=warning,
                created=False,
            )
        try:
            conn.execute(
                "INSERT INTO teacher_roster(teacher_id, subject_id, class_name) VALUES (?, ?, ?)",
                (tid, sid, class_text),
            )
        except sqlite3.IntegrityError:
            return _fail("class_already_owned")
    payload = _ok(
        teacher_id=tid,
        subject_id=sid,
        class_name=class_text,
        created=True,
    )
    if warning:
        payload["warning"] = warning
    return payload


def remove_roster(
    store: Any,
    *,
    teacher_id: str,
    subject_id: str,
    class_name: str,
) -> Dict[str, Any]:
    tid = _text(teacher_id)
    sid = _text(subject_id)
    class_text = _text(class_name)
    if not tid or not sid or not class_text:
        return _fail("missing_class_name" if not class_text else "missing_subject_id")
    with store._connect() as conn:
        owner = _roster_owner(conn, subject_id=sid, class_name=class_text)
        if owner is None or owner != tid:
            return _fail("not_found")
        if _count_enrollments(conn, subject_id=sid, class_name=class_text) > 0:
            return _fail("enrollments_remain")
        conn.execute(
            "DELETE FROM teacher_roster WHERE teacher_id = ? AND subject_id = ? AND class_name = ?",
            (tid, sid, class_text),
        )
    return _ok(teacher_id=tid, subject_id=sid, class_name=class_text, removed=True)


def list_roster(store: Any, *, teacher_id: Optional[str] = None) -> Dict[str, Any]:
    tid = _text(teacher_id)
    sql = (
        "SELECT teacher_id, subject_id, class_name FROM teacher_roster"
    )
    params: Sequence[str] = ()
    if tid:
        sql += " WHERE teacher_id = ?"
        params = (tid,)
    sql += " ORDER BY teacher_id, subject_id, class_name"
    with store._connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    items = [
        {
            "teacher_id": _text(row["teacher_id"]),
            "subject_id": _text(row["subject_id"]),
            "class_name": _text(row["class_name"]),
        }
        for row in rows
    ]
    return _ok(count=len(items), items=items)


def _require_owner(
    conn: sqlite3.Connection, *, teacher_id: str, subject_id: str, class_name: str
) -> Optional[str]:
    owner = _roster_owner(conn, subject_id=subject_id, class_name=class_name)
    if owner is None:
        return "roster_required"
    if teacher_id and owner != teacher_id:
        return "roster_required"
    return None


def _import_class_from_student_auth(
    conn: sqlite3.Connection,
    *,
    teacher_id: str,
    subject_id: str,
    class_name: str,
) -> int:
    class_norm = normalize(class_name)
    students = conn.execute(
        (
            "SELECT student_id FROM student_auth "
            "WHERE class_name = ? OR class_norm = ? ORDER BY student_id"
        ),
        (class_name, class_norm),
    ).fetchall()
    inserted = 0
    for row in students:
        student_id = _text(row["student_id"])
        if not student_id:
            continue
        if _insert_enrollment(
            conn,
            student_id=student_id,
            subject_id=subject_id,
            class_name=class_name,
            teacher_id=teacher_id,
        ):
            inserted += 1
    return inserted


def enroll_class(
    store: Any,
    *,
    teacher_id: str,
    subject_id: str,
    class_name: str,
    resync: bool = False,
) -> Dict[str, Any]:
    tid = _text(teacher_id)
    sid = _text(subject_id)
    class_text = _text(class_name)
    if not tid or not sid or not class_text:
        return _fail("missing_class_name" if not class_text else "missing_teacher_id")
    with store._connect() as conn:
        owner_error = _require_owner(
            conn, teacher_id=tid, subject_id=sid, class_name=class_text
        )
        if owner_error:
            return _fail(owner_error)
        already = _count_enrollments(conn, subject_id=sid, class_name=class_text)
        if already > 0 and not resync:
            skip_bootstrap = True
            inserted = 0
        else:
            skip_bootstrap = False
            inserted = _import_class_from_student_auth(
                conn, teacher_id=tid, subject_id=sid, class_name=class_text
            )
    listed = list_enrollments(store, subject_id=sid, class_name=class_text)
    items = listed.get("items") or []
    return _ok(
        teacher_id=tid,
        subject_id=sid,
        class_name=class_text,
        count=len(items) if skip_bootstrap else inserted,
        items=items,
        source="enrollments" if skip_bootstrap else "student_auth",
        bootstrapped=not skip_bootstrap,
    )


def enroll(
    store: Any,
    *,
    student_id: str,
    subject_id: str,
    class_name: str,
    teacher_id: str = "",
) -> Dict[str, Any]:
    sid_student = _text(student_id)
    sid = _text(subject_id)
    class_text = _text(class_name)
    tid = _text(teacher_id)
    if not sid_student:
        return _fail("missing_student_id")
    if not sid:
        return _fail("missing_subject_id")
    if not class_text:
        return _fail("missing_class_name")
    with store._connect() as conn:
        if not _student_exists(conn, sid_student):
            return _fail("student_not_found")
        owner = _roster_owner(conn, subject_id=sid, class_name=class_text)
        if owner is None:
            return _fail("roster_required")
        if tid and tid != owner:
            return _fail("roster_required")
        created = _insert_enrollment(
            conn,
            student_id=sid_student,
            subject_id=sid,
            class_name=class_text,
            teacher_id=owner,
        )
    return _ok(
        student_id=sid_student,
        subject_id=sid,
        class_name=class_text,
        teacher_id=owner,
        created=created,
    )


def _insert_enrollment(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    subject_id: str,
    class_name: str,
    teacher_id: str,
) -> bool:
    try:
        conn.execute(
            (
                "INSERT INTO student_enrollments"
                "(student_id, subject_id, class_name, teacher_id) VALUES (?, ?, ?, ?)"
            ),
            (student_id, subject_id, class_name, teacher_id),
        )
        return True
    except sqlite3.IntegrityError:
        conn.execute(
            (
                "UPDATE student_enrollments SET teacher_id = ? "
                "WHERE student_id = ? AND subject_id = ? AND class_name = ?"
            ),
            (teacher_id, student_id, subject_id, class_name),
        )
        return False


def unenroll(
    store: Any,
    *,
    student_id: str,
    subject_id: str,
    class_name: str,
) -> Dict[str, Any]:
    sid_student = _text(student_id)
    sid = _text(subject_id)
    class_text = _text(class_name)
    if not sid_student or not sid or not class_text:
        return _fail("missing_student_id")
    with store._connect() as conn:
        cursor = conn.execute(
            (
                "DELETE FROM student_enrollments "
                "WHERE student_id = ? AND subject_id = ? AND class_name = ?"
            ),
            (sid_student, sid, class_text),
        )
        if int(cursor.rowcount or 0) <= 0:
            return _fail("not_found")
    return _ok(student_id=sid_student, subject_id=sid, class_name=class_text, removed=True)


def list_enrollments(
    store: Any,
    *,
    subject_id: str,
    class_name: str,
) -> Dict[str, Any]:
    sid = _text(subject_id)
    class_text = _text(class_name)
    if not sid:
        return _fail("missing_subject_id")
    if not class_text:
        return _fail("missing_class_name")
    with store._connect() as conn:
        rows = conn.execute(
            (
                "SELECT student_id, subject_id, class_name, teacher_id "
                "FROM student_enrollments WHERE subject_id = ? AND class_name = ? "
                "ORDER BY student_id"
            ),
            (sid, class_text),
        ).fetchall()
    items = [
        {
            "student_id": _text(row["student_id"]),
            "subject_id": _text(row["subject_id"]),
            "class_name": _text(row["class_name"]),
            "teacher_id": _text(row["teacher_id"]),
        }
        for row in rows
    ]
    return _ok(count=len(items), items=items)


def bulk_move_enrollments(
    store: Any,
    *,
    subject_id: str,
    from_class: str,
    to_class: str,
    student_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    sid = _text(subject_id)
    src = _text(from_class)
    dest = _text(to_class)
    if not sid or not src or not dest:
        return _fail("missing_class_name")
    if src == dest:
        return _ok(count=0, subject_id=sid, from_class=src, to_class=dest)
    requested = [_text(item) for item in (student_ids or []) if _text(item)]
    with store._connect() as conn:
        dest_owner = _roster_owner(conn, subject_id=sid, class_name=dest)
        if dest_owner is None:
            return _fail("roster_required")
        movers = _select_move_targets(
            conn, subject_id=sid, from_class=src, student_ids=requested
        )
        moved = 0
        for student_id in movers:
            if _move_one_enrollment(
                conn,
                student_id=student_id,
                subject_id=sid,
                from_class=src,
                to_class=dest,
                teacher_id=dest_owner,
            ):
                moved += 1
    return _ok(
        count=moved,
        subject_id=sid,
        from_class=src,
        to_class=dest,
        teacher_id=dest_owner,
    )


def _select_move_targets(
    conn: sqlite3.Connection,
    *,
    subject_id: str,
    from_class: str,
    student_ids: Sequence[str],
) -> List[str]:
    if student_ids:
        return list(student_ids)
    rows = conn.execute(
        (
            "SELECT student_id FROM student_enrollments "
            "WHERE subject_id = ? AND class_name = ? ORDER BY student_id"
        ),
        (subject_id, from_class),
    ).fetchall()
    return [_text(row["student_id"]) for row in rows if _text(row["student_id"])]


def _move_one_enrollment(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    subject_id: str,
    from_class: str,
    to_class: str,
    teacher_id: str,
) -> bool:
    existing = conn.execute(
        (
            "SELECT 1 FROM student_enrollments "
            "WHERE student_id = ? AND subject_id = ? AND class_name = ?"
        ),
        (student_id, subject_id, from_class),
    ).fetchone()
    if existing is None:
        return False
    conn.execute(
        (
            "DELETE FROM student_enrollments "
            "WHERE student_id = ? AND subject_id = ? AND class_name = ?"
        ),
        (student_id, subject_id, from_class),
    )
    _insert_enrollment(
        conn,
        student_id=student_id,
        subject_id=subject_id,
        class_name=to_class,
        teacher_id=teacher_id,
    )
    return True


def rename_class(
    store: Any,
    *,
    subject_id: str,
    old_class_name: str,
    new_class_name: str,
) -> Dict[str, Any]:
    sid = _text(subject_id)
    old_name = _text(old_class_name)
    new_name = _text(new_class_name)
    if not sid or not old_name or not new_name:
        return _fail("missing_class_name")
    if old_name == new_name:
        return _ok(subject_id=sid, class_name=new_name, renamed=False)
    with store._connect() as conn:
        owner = _roster_owner(conn, subject_id=sid, class_name=old_name)
        if owner is None:
            return _fail("not_found")
        dest_owner = _roster_owner(conn, subject_id=sid, class_name=new_name)
        if dest_owner is not None:
            return _fail("class_already_owned")
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                (
                    "UPDATE teacher_roster SET class_name = ? "
                    "WHERE subject_id = ? AND class_name = ?"
                ),
                (new_name, sid, old_name),
            )
            conn.execute(
                (
                    "UPDATE student_enrollments SET class_name = ? "
                    "WHERE subject_id = ? AND class_name = ?"
                ),
                (new_name, sid, old_name),
            )
            conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            return _fail("class_already_owned")
    return _ok(
        subject_id=sid,
        from_class=old_name,
        to_class=new_name,
        teacher_id=owner,
        renamed=True,
    )


def list_enrollment_student_ids(
    store: Any,
    *,
    teacher_id: str,
    subject_id: str,
    class_name: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> List[str]:
    tid = _text(teacher_id)
    sid = _text(subject_id)
    class_text = _text(class_name)
    sql = (
        "SELECT DISTINCT student_id FROM student_enrollments "
        "WHERE teacher_id = ? AND subject_id = ?"
    )
    params: List[str] = [tid, sid]
    if class_text:
        sql += " AND class_name = ?"
        params.append(class_text)
    sql += " ORDER BY student_id"
    with _borrow_conn(store, conn) as used:
        rows = used.execute(sql, params).fetchall()
    return [_text(row["student_id"]) for row in rows if _text(row["student_id"])]


def list_roster_class_names(
    store: Any,
    *,
    teacher_id: str,
    subject_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> List[str]:
    tid = _text(teacher_id)
    sid = _text(subject_id)
    with _borrow_conn(store, conn) as used:
        rows = used.execute(
            (
                "SELECT class_name FROM teacher_roster "
                "WHERE teacher_id = ? AND subject_id = ? ORDER BY class_name"
            ),
            (tid, sid),
        ).fetchall()
    return [_text(row["class_name"]) for row in rows if _text(row["class_name"])]


def student_enrolled(
    store: Any,
    *,
    student_id: str,
    teacher_id: str,
    subject_id: str = "",
    class_name: str = "",
    conn: Optional[sqlite3.Connection] = None,
) -> bool:
    sid = _text(student_id)
    tid = _text(teacher_id)
    subject = _text(subject_id)
    class_text = _text(class_name)
    sql = "SELECT 1 FROM student_enrollments WHERE student_id = ? AND teacher_id = ?"
    params: List[str] = [sid, tid]
    if subject:
        sql += " AND subject_id = ?"
        params.append(subject)
    if class_text:
        sql += " AND class_name = ?"
        params.append(class_text)
    with _borrow_conn(store, conn) as used:
        row = used.execute(sql, params).fetchone()
    return row is not None


def resolve_expected_students(
    store: Any,
    *,
    scope: str,
    class_name: str,
    student_ids: Iterable[str],
    teacher_id: str,
    subject_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    tid = _text(teacher_id)
    sid = _text(subject_id)
    scope_val = _text(scope).lower() or "public"
    class_text = _text(class_name)
    requested = [_text(item) for item in student_ids if _text(item)]
    if not tid or not sid:
        return _fail("roster_required")
    if scope_val == "student":
        return _resolve_student_scope(
            store, teacher_id=tid, subject_id=sid, student_ids=requested, conn=conn
        )
    if scope_val == "class":
        return _resolve_class_scope(
            store, teacher_id=tid, subject_id=sid, class_name=class_text, conn=conn
        )
    return _resolve_public_scope(store, teacher_id=tid, subject_id=sid, conn=conn)


def _resolve_public_scope(
    store: Any,
    *,
    teacher_id: str,
    subject_id: str,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    classes = list_roster_class_names(
        store, teacher_id=teacher_id, subject_id=subject_id, conn=conn
    )
    if not classes:
        return _fail("roster_required")
    items = list_enrollment_student_ids(
        store, teacher_id=teacher_id, subject_id=subject_id, conn=conn
    )
    if not items:
        return _fail("enrollment_empty")
    return _ok(items=items, classes=classes)


def _resolve_class_scope(
    store: Any,
    *,
    teacher_id: str,
    subject_id: str,
    class_name: str,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    if not class_name:
        return _fail("missing_class_name")
    with _borrow_conn(store, conn) as used:
        owner_error = _require_owner(
            used, teacher_id=teacher_id, subject_id=subject_id, class_name=class_name
        )
        if owner_error:
            return _fail(owner_error)
    items = list_enrollment_student_ids(
        store,
        teacher_id=teacher_id,
        subject_id=subject_id,
        class_name=class_name,
        conn=conn,
    )
    if not items:
        return _fail("enrollment_empty")
    return _ok(items=items)


def _resolve_student_scope(
    store: Any,
    *,
    teacher_id: str,
    subject_id: str,
    student_ids: Sequence[str],
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    classes = list_roster_class_names(
        store, teacher_id=teacher_id, subject_id=subject_id, conn=conn
    )
    if not classes:
        return _fail("roster_required")
    if not student_ids:
        return _fail("enrollment_empty")
    missing = [
        sid
        for sid in student_ids
        if not student_enrolled(
            store,
            student_id=sid,
            teacher_id=teacher_id,
            subject_id=subject_id,
            conn=conn,
        )
    ]
    if missing:
        return _fail("student_not_enrolled", missing=missing)
    return _ok(items=sorted(dict.fromkeys(student_ids)))


def list_class_reset_targets(
    store: Any,
    *,
    class_name: str,
    actor_id: str,
    actor_role: str,
) -> Dict[str, Any]:
    class_text = _text(class_name)
    if not class_text:
        return _fail("missing_class_name")
    role = _text(actor_role).lower()
    tid = _text(actor_id)
    with store._connect() as conn:
        if role != "admin":
            owned = conn.execute(
                "SELECT 1 FROM teacher_roster WHERE teacher_id = ? AND class_name = ?",
                (tid, class_text),
            ).fetchone()
            if owned is None:
                return _fail("roster_required")
            rows = conn.execute(
                (
                    "SELECT DISTINCT e.student_id, COALESCE(s.student_name, e.student_id) AS student_name, "
                    "e.class_name FROM student_enrollments e "
                    "LEFT JOIN student_auth s ON s.student_id = e.student_id "
                    "WHERE e.class_name = ? AND e.teacher_id = ? ORDER BY e.student_id"
                ),
                (class_text, tid),
            ).fetchall()
        else:
            rows = conn.execute(
                (
                    "SELECT DISTINCT e.student_id, COALESCE(s.student_name, e.student_id) AS student_name, "
                    "e.class_name FROM student_enrollments e "
                    "LEFT JOIN student_auth s ON s.student_id = e.student_id "
                    "WHERE e.class_name = ? ORDER BY e.student_id"
                ),
                (class_text,),
            ).fetchall()
    items = [
        {
            "student_id": _text(row["student_id"]),
            "student_name": _text(row["student_name"]),
            "class_name": _text(row["class_name"]),
        }
        for row in rows
        if _text(row["student_id"])
    ]
    if not items:
        return _fail("not_found")
    return _ok(scope="class", items=items)


class IdentityGraphMixin:
    def seed_subjects(self, *, packs_root: Optional[Path] = None) -> Dict[str, Any]:
        return seed_subjects(self, packs_root=packs_root)

    def list_subjects(self) -> Dict[str, Any]:
        return list_subjects(self)

    def add_subject(
        self,
        *,
        subject_id: str,
        display_name: str,
        pack_id: str = "",
    ) -> Dict[str, Any]:
        return add_subject(
            self, subject_id=subject_id, display_name=display_name, pack_id=pack_id
        )

    def add_roster(
        self,
        *,
        teacher_id: str,
        subject_id: str,
        class_name: str,
        allow_empty: bool = True,
    ) -> Dict[str, Any]:
        return add_roster(
            self,
            teacher_id=teacher_id,
            subject_id=subject_id,
            class_name=class_name,
            allow_empty=allow_empty,
        )

    def remove_roster(
        self,
        *,
        teacher_id: str,
        subject_id: str,
        class_name: str,
    ) -> Dict[str, Any]:
        return remove_roster(
            self, teacher_id=teacher_id, subject_id=subject_id, class_name=class_name
        )

    def list_roster(self, *, teacher_id: Optional[str] = None) -> Dict[str, Any]:
        return list_roster(self, teacher_id=teacher_id)

    def enroll_class(
        self,
        *,
        teacher_id: str,
        subject_id: str,
        class_name: str,
        resync: bool = False,
    ) -> Dict[str, Any]:
        return enroll_class(
            self,
            teacher_id=teacher_id,
            subject_id=subject_id,
            class_name=class_name,
            resync=resync,
        )

    def enroll(
        self,
        *,
        student_id: str,
        subject_id: str,
        class_name: str,
        teacher_id: str = "",
    ) -> Dict[str, Any]:
        return enroll(
            self,
            student_id=student_id,
            subject_id=subject_id,
            class_name=class_name,
            teacher_id=teacher_id,
        )

    def unenroll(
        self,
        *,
        student_id: str,
        subject_id: str,
        class_name: str,
    ) -> Dict[str, Any]:
        return unenroll(
            self, student_id=student_id, subject_id=subject_id, class_name=class_name
        )

    def bulk_move_enrollments(
        self,
        *,
        subject_id: str,
        from_class: str,
        to_class: str,
        student_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        return bulk_move_enrollments(
            self,
            subject_id=subject_id,
            from_class=from_class,
            to_class=to_class,
            student_ids=student_ids,
        )

    def rename_class(
        self,
        *,
        subject_id: str,
        old_class_name: str,
        new_class_name: str,
    ) -> Dict[str, Any]:
        return rename_class(
            self,
            subject_id=subject_id,
            old_class_name=old_class_name,
            new_class_name=new_class_name,
        )

    def list_enrollments(self, *, subject_id: str, class_name: str) -> Dict[str, Any]:
        return list_enrollments(self, subject_id=subject_id, class_name=class_name)

    def resolve_expected_students(
        self,
        *,
        scope: str,
        class_name: str,
        student_ids: Sequence[str],
        teacher_id: str,
        subject_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        return resolve_expected_students(
            self,
            scope=scope,
            class_name=class_name,
            student_ids=student_ids,
            teacher_id=teacher_id,
            subject_id=subject_id,
            conn=conn,
        )


def conflict_status(error: str) -> int:
    if error in _CONFLICT_ERRORS:
        return 409
    if error in {"not_found", "subject_not_found", "teacher_not_found", "student_not_found"}:
        return 404
    if error in {"forbidden"}:
        return 403
    return 400
