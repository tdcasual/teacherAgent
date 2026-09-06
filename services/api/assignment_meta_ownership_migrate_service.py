from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .auth_registry_service import build_auth_registry_store
from .core_utils import parse_ids_value, resolve_scope
from .fs_atomic import atomic_write_json, atomic_write_text
from .settings import default_teacher_id

REQUIRED_TABLES = ("subjects", "teacher_roster", "student_enrollments")
REQUIRED_SEED_SUBJECTS = ("generic", "physics")
TERMINAL_VISIBILITY = frozenset({"published", "archived", "orphan_draft", "retired_auto"})
SUBJECT_ALIASES = {
    "物理": "physics",
    "数学": "math",
    "通用": "generic",
}
COUNT_KEYS = (
    "migrated",
    "skipped",
    "orphan",
    "needs_subject_review",
    "needs_roster_review",
    "retired_auto",
)


class MigrationPreflightError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = str(code or "roster_tables_missing")


class AssignmentClaimError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "claim_failed")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "on"}


def forbidden_teacher_ids() -> frozenset[str]:
    ids = {"teacher"}
    default = _text(default_teacher_id())
    if default:
        ids.add(default)
    return frozenset(ids)


def is_legal_teacher_id(teacher_id: Any) -> bool:
    tid = _text(teacher_id)
    return bool(tid) and tid not in forbidden_teacher_ids()


def _auth_db_path(data_dir: Path) -> Path:
    return Path(data_dir) / "auth" / "auth_registry.sqlite3"


def _connect_auth_ro(data_dir: Path) -> sqlite3.Connection:
    db_path = _auth_db_path(data_dir)
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _visibility_status(meta: Dict[str, Any]) -> str:
    return _text(meta.get("visibility_status")).casefold()


def _meta_scope(meta: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    student_ids = parse_ids_value(meta.get("student_ids") or [])
    class_name = _text(meta.get("class_name"))
    scope_val = resolve_scope(_text(meta.get("scope")), student_ids, class_name)
    return scope_val, class_name, student_ids


def _pragma_table_names(conn: sqlite3.Connection) -> set[str]:
    names: set[str] = set()
    for table in REQUIRED_TABLES:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if rows:
            names.add(table)
    return names


def preflight_roster_tables(data_dir: Path) -> Path:
    db_path = _auth_db_path(data_dir)
    if not db_path.is_file():
        raise MigrationPreflightError("roster_tables_missing")
    uri = f"file:{db_path.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise MigrationPreflightError("roster_tables_missing") from exc
    try:
        conn.row_factory = sqlite3.Row
        present = _pragma_table_names(conn)
        if present != set(REQUIRED_TABLES):
            raise MigrationPreflightError("roster_tables_missing")
        rows = conn.execute(
            "SELECT subject_id FROM subjects WHERE subject_id IN (?, ?)",
            REQUIRED_SEED_SUBJECTS,
        ).fetchall()
        found = {_text(row["subject_id"]) for row in rows}
        if set(REQUIRED_SEED_SUBJECTS) - found:
            raise MigrationPreflightError("subjects_seed_missing")
    finally:
        conn.close()
    return db_path


def _load_json_object(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_subject_index(data_dir: Path) -> Dict[str, Dict[str, str]]:
    conn = _connect_auth_ro(data_dir)
    try:
        rows = conn.execute(
            "SELECT subject_id, display_name, pack_id FROM subjects"
        ).fetchall()
    finally:
        conn.close()
    index: Dict[str, Dict[str, str]] = {}
    for row in rows:
        sid = _text(row["subject_id"])
        if sid:
            index[sid] = {
                "subject_id": sid,
                "display_name": _text(row["display_name"]),
                "pack_id": _text(row["pack_id"]) or sid,
            }
    return index


def _safe_job_dir_name(job_id: str) -> str:
    raw = _text(job_id)
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    return safe or "job"


def load_job_teacher_id(uploads_dir: Path, job_id: str) -> str:
    job_path = Path(uploads_dir) / "assignment_jobs" / _safe_job_dir_name(job_id) / "job.json"
    job = _load_json_object(job_path)
    teacher_id = _text(job.get("teacher_id"))
    return teacher_id if is_legal_teacher_id(teacher_id) else ""


def resolve_migration_teacher_id(meta: Dict[str, Any], uploads_dir: Path) -> str:
    current = _text(meta.get("teacher_id"))
    if is_legal_teacher_id(current):
        return current
    job_id = _text(meta.get("job_id"))
    if job_id:
        from_job = load_job_teacher_id(uploads_dir, job_id)
        if is_legal_teacher_id(from_job):
            return from_job
    return ""


def _subject_candidates(
    meta: Dict[str, Any], requirements: Dict[str, Any], *, reviewing: bool
) -> List[str]:
    current = _text(meta.get("subject_id"))
    tokens = [
        _text(meta.get("unmapped_subject")),
        _text(requirements.get("subject")),
        _text(requirements.get("subject_id")),
    ]
    if reviewing:
        if current and current != "generic":
            tokens.append(current)
    else:
        tokens.insert(0, current)
    return tokens


def map_subject_id(
    candidates: Iterable[str], subject_index: Dict[str, Dict[str, str]]
) -> Tuple[str, bool, str]:
    ids = set(subject_index)
    unmapped = ""
    for raw in candidates:
        token = _text(raw)
        if not token:
            continue
        if not unmapped:
            unmapped = token
        if token in ids:
            return token, False, ""
        alias = SUBJECT_ALIASES.get(token)
        if alias and alias in ids:
            return alias, False, ""
    return "generic", True, unmapped


def _empty_counts() -> Dict[str, int]:
    return {key: 0 for key in COUNT_KEYS}


def _should_skip(meta: Dict[str, Any], subject_index: Dict[str, Dict[str, str]]) -> bool:
    if not is_legal_teacher_id(meta.get("teacher_id")):
        return False
    if _text(meta.get("subject_id")) not in subject_index:
        return False
    if _visibility_status(meta) not in TERMINAL_VISIBILITY:
        return False
    if _truthy_flag(meta.get("needs_subject_review")):
        return False
    if _truthy_flag(meta.get("needs_roster_review")):
        return False
    return True


def _ensure_policy_v2(meta: Dict[str, Any]) -> None:
    # Design: ownership migration backfills policy v2. A missing
    # requires_discussion must not keep the progress-service implicit True.
    # Explicit True is preserved.
    raw = meta.get("completion_policy")
    policy = dict(raw) if isinstance(raw, dict) else {}
    if "requires_discussion" not in policy:
        policy["requires_discussion"] = False
    policy.setdefault("requires_submission", True)
    policy.setdefault("min_graded_total", 1)
    policy.setdefault("best_attempt", "score_earned_then_correct_then_graded_total")
    if "version" not in policy:
        policy["version"] = 2
    meta["completion_policy"] = policy


def _keep_empty_due_at(meta: Dict[str, Any]) -> None:
    due_at = meta.get("due_at")
    if due_at is None or _text(due_at) == "":
        meta["due_at"] = ""


def _apply_subject_mapping(
    meta: Dict[str, Any],
    *,
    requirements: Dict[str, Any],
    subject_index: Dict[str, Dict[str, str]],
) -> None:
    reviewing = _truthy_flag(meta.get("needs_subject_review"))
    subject_id, needs_review, unmapped = map_subject_id(
        _subject_candidates(meta, requirements, reviewing=reviewing),
        subject_index,
    )
    meta["subject_id"] = subject_id
    pack = subject_index.get(subject_id) or {}
    meta["pack_id"] = pack.get("pack_id") or subject_id
    if needs_review:
        meta["needs_subject_review"] = True
        if unmapped and unmapped != "generic":
            meta["unmapped_subject"] = unmapped
        elif not _text(meta.get("unmapped_subject")):
            meta.pop("unmapped_subject", None)
        return
    meta.pop("needs_subject_review", None)
    meta.pop("unmapped_subject", None)


def _public_expected_students_ro(
    data_dir: Path, *, teacher_id: str, subject_id: str
) -> List[str]:
    conn = _connect_auth_ro(data_dir)
    try:
        classes = conn.execute(
            "SELECT 1 FROM teacher_roster WHERE teacher_id = ? AND subject_id = ? LIMIT 1",
            (teacher_id, subject_id),
        ).fetchone()
        if classes is None:
            return []
        rows = conn.execute(
            "SELECT DISTINCT student_id FROM student_enrollments "
            "WHERE teacher_id = ? AND subject_id = ? ORDER BY student_id",
            (teacher_id, subject_id),
        ).fetchall()
    finally:
        conn.close()
    return [_text(row["student_id"]) for row in rows if _text(row["student_id"])]


def _recompute_public_expected(
    meta: Dict[str, Any], *, data_dir: Path, teacher_id: str, subject_id: str
) -> None:
    scope_val, _class_name, _student_ids = _meta_scope(meta)
    if scope_val != "public":
        return
    if not teacher_id or not subject_id:
        meta["needs_roster_review"] = True
        return
    items = _public_expected_students_ro(
        data_dir, teacher_id=teacher_id, subject_id=subject_id
    )
    if not items:
        meta["needs_roster_review"] = True
        return
    meta["expected_students"] = items
    meta.pop("needs_roster_review", None)


def _assign_visibility(meta: Dict[str, Any], *, teacher_id: str) -> None:
    source = _text(meta.get("source")).lower()
    current = _visibility_status(meta)
    needs_review = _truthy_flag(meta.get("needs_subject_review")) or _truthy_flag(
        meta.get("needs_roster_review")
    )
    if source == "auto":
        meta["visibility_status"] = "retired_auto"
        return
    if not teacher_id:
        meta["visibility_status"] = "orphan_draft"
        meta.pop("teacher_id", None)
        return
    if needs_review:
        meta["visibility_status"] = "draft" if current in {"", "published"} else current
        return
    if current in TERMINAL_VISIBILITY or current == "draft":
        meta["visibility_status"] = current
        return
    meta["visibility_status"] = "published"


def migrate_one_meta(
    meta: Dict[str, Any],
    *,
    folder: Path,
    uploads_dir: Path,
    data_dir: Path,
    subject_index: Dict[str, Dict[str, str]],
) -> Tuple[Dict[str, Any], bool]:
    if _should_skip(meta, subject_index):
        return meta, True
    updated = dict(meta)
    if not _text(updated.get("assignment_id")):
        updated["assignment_id"] = folder.name
    teacher_id = resolve_migration_teacher_id(updated, uploads_dir)
    if teacher_id:
        updated["teacher_id"] = teacher_id
    else:
        updated.pop("teacher_id", None)
    requirements = _load_json_object(folder / "requirements.json")
    _apply_subject_mapping(updated, requirements=requirements, subject_index=subject_index)
    _ensure_policy_v2(updated)
    _keep_empty_due_at(updated)
    if teacher_id:
        _recompute_public_expected(
            updated,
            data_dir=data_dir,
            teacher_id=teacher_id,
            subject_id=_text(updated.get("subject_id")),
        )
    _assign_visibility(updated, teacher_id=teacher_id)
    if _truthy_flag(updated.get("needs_subject_review")) or _truthy_flag(
        updated.get("needs_roster_review")
    ):
        if _visibility_status(updated) == "published":
            updated["visibility_status"] = "draft"
    return updated, False


def _classify(counts: Dict[str, int], meta: Dict[str, Any], *, skipped: bool) -> None:
    if skipped:
        counts["skipped"] += 1
        return
    counts["migrated"] += 1
    status = _visibility_status(meta)
    if status == "orphan_draft":
        counts["orphan"] += 1
    if _truthy_flag(meta.get("needs_subject_review")):
        counts["needs_subject_review"] += 1
    if _truthy_flag(meta.get("needs_roster_review")):
        counts["needs_roster_review"] += 1
    if status == "retired_auto":
        counts["retired_auto"] += 1


def _iter_assignment_folders(data_dir: Path) -> List[Path]:
    root = Path(data_dir) / "assignments"
    if not root.is_dir():
        return []
    folders = [path for path in root.iterdir() if path.is_dir() and (path / "meta.json").is_file()]
    return sorted(folders, key=lambda path: path.name)


def _write_meta_with_bak(folder: Path, updated: Dict[str, Any]) -> None:
    bak_path = folder / "meta.json.bak"
    meta_path = folder / "meta.json"
    if not bak_path.exists():
        atomic_write_text(bak_path, meta_path.read_text(encoding="utf-8"))
    atomic_write_json(meta_path, updated)


def migrate_assignment_meta_ownership(
    *,
    data_dir: Path,
    uploads_dir: Path,
    apply: bool = False,
) -> Dict[str, Any]:
    data_root = Path(data_dir)
    uploads_root = Path(uploads_dir)
    preflight_roster_tables(data_root)
    subject_index = load_subject_index(data_root)
    counts = _empty_counts()
    items: List[Dict[str, Any]] = []
    for folder in _iter_assignment_folders(data_root):
        original = _load_json_object(folder / "meta.json")
        if not original:
            counts["skipped"] += 1
            continue
        updated, skipped = migrate_one_meta(
            original,
            folder=folder,
            uploads_dir=uploads_root,
            data_dir=data_root,
            subject_index=subject_index,
        )
        _classify(counts, updated, skipped=skipped)
        changed = (not skipped) and updated != original
        if apply and changed:
            _write_meta_with_bak(folder, updated)
        items.append(
            {
                "assignment_id": _text(updated.get("assignment_id")) or folder.name,
                "skipped": skipped,
                "visibility_status": _text(updated.get("visibility_status")),
                "needs_subject_review": _truthy_flag(updated.get("needs_subject_review")),
                "needs_roster_review": _truthy_flag(updated.get("needs_roster_review")),
            }
        )
    return {"ok": True, "apply": bool(apply), "counts": counts, "items": items}


def list_orphan_assignments(data_dir: Path) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for folder in _iter_assignment_folders(Path(data_dir)):
        meta = _load_json_object(folder / "meta.json")
        if _visibility_status(meta) != "orphan_draft":
            continue
        items.append(
            {
                "assignment_id": _text(meta.get("assignment_id")) or folder.name,
                "teacher_id": _text(meta.get("teacher_id")),
                "subject_id": _text(meta.get("subject_id")),
                "visibility_status": "orphan_draft",
                "needs_subject_review": _truthy_flag(meta.get("needs_subject_review")),
                "needs_roster_review": _truthy_flag(meta.get("needs_roster_review")),
                "scope": _text(meta.get("scope")),
            }
        )
    return {"ok": True, "count": len(items), "items": items}


def _resolve_assignment_folder(assignment_id: str, data_dir: Path) -> Path:
    aid = _text(assignment_id)
    if not aid:
        raise AssignmentClaimError(400, "assignment_id is required")
    root = (Path(data_dir) / "assignments").resolve()
    folder = (root / aid).resolve()
    if folder != root and root not in folder.parents:
        raise AssignmentClaimError(400, "invalid assignment_id")
    return folder


def _require_claim_roster(
    store: Any, *, teacher_id: str, subject_id: str, meta: Dict[str, Any]
) -> None:
    from .auth.identity_graph_service import list_roster_class_names

    classes = list_roster_class_names(store, teacher_id=teacher_id, subject_id=subject_id)
    if not classes:
        raise AssignmentClaimError(400, "roster_required")
    scope_val, class_name, _student_ids = _meta_scope(meta)
    if scope_val == "class" and class_name and class_name not in classes:
        raise AssignmentClaimError(400, "roster_required")


def _claimed_expected_students(
    store: Any,
    meta: Dict[str, Any],
    *,
    teacher_id: str,
    subject_id: str,
    visibility_status: str,
) -> List[str]:
    scope_val, class_name, student_ids = _meta_scope(meta)
    result = store.resolve_expected_students(
        scope=scope_val,
        class_name=class_name,
        student_ids=student_ids,
        teacher_id=teacher_id,
        subject_id=subject_id,
    )
    if result.get("ok"):
        return [_text(item) for item in list(result.get("items") or []) if _text(item)]
    if visibility_status == "published":
        raise AssignmentClaimError(400, str(result.get("error") or "roster_required"))
    return []


def claim_assignment(
    assignment_id: str,
    *,
    teacher_id: str,
    subject_id: str,
    visibility_status: str = "draft",
    data_dir: Path,
    principal_actor_id: str = "",
    principal_role: str = "",
) -> Dict[str, Any]:
    tid = _text(teacher_id)
    sid = _text(subject_id)
    vis = _text(visibility_status) or "draft"
    if vis not in {"draft", "published"}:
        raise AssignmentClaimError(400, "invalid_visibility_status")
    if not is_legal_teacher_id(tid):
        raise AssignmentClaimError(400, "default_teacher_id_forbidden")
    if not sid:
        raise AssignmentClaimError(400, "subject_id_required")

    folder = _resolve_assignment_folder(assignment_id, Path(data_dir))
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        raise AssignmentClaimError(404, "assignment not found")
    meta = _load_json_object(meta_path)
    if _visibility_status(meta) != "orphan_draft":
        raise AssignmentClaimError(409, "not_orphan")

    store = build_auth_registry_store(data_dir=Path(data_dir))
    subjects = {_text(item.get("subject_id")) for item in store.list_subjects().get("items") or []}
    if sid not in subjects:
        raise AssignmentClaimError(400, "subject_not_found")
    with store._connect() as conn:
        teacher_row = conn.execute(
            "SELECT 1 FROM teacher_auth WHERE teacher_id = ?", (tid,)
        ).fetchone()
    if teacher_row is None:
        raise AssignmentClaimError(404, "teacher_not_found")
    _require_claim_roster(store, teacher_id=tid, subject_id=sid, meta=meta)
    expected = _claimed_expected_students(
        store, meta, teacher_id=tid, subject_id=sid, visibility_status=vis
    )
    pack_id = sid
    for item in store.list_subjects().get("items") or []:
        if _text(item.get("subject_id")) == sid:
            pack_id = _text(item.get("pack_id")) or sid
            break
    meta["teacher_id"] = tid
    meta["subject_id"] = sid
    meta["pack_id"] = pack_id
    meta["visibility_status"] = vis
    meta.pop("needs_subject_review", None)
    meta.pop("needs_roster_review", None)
    meta.pop("unmapped_subject", None)
    if expected:
        meta["expected_students"] = expected
    _ensure_policy_v2(meta)
    _keep_empty_due_at(meta)
    atomic_write_json(meta_path, meta)
    with store._connect() as conn:
        store._append_audit(
            conn,
            actor_id=_text(principal_actor_id),
            actor_role=_text(principal_role),
            action="assignment_claim",
            target_id=_text(assignment_id) or folder.name,
            target_role="assignment",
            detail={"teacher_id": tid, "subject_id": sid, "visibility_status": vis},
        )
    return {
        "ok": True,
        "assignment_id": _text(meta.get("assignment_id")) or folder.name,
        "teacher_id": tid,
        "subject_id": sid,
        "visibility_status": vis,
        "expected_students": list(meta.get("expected_students") or []),
    }
