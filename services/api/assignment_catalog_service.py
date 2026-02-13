from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

_log = logging.getLogger(__name__)
_DEFAULT_LIST_LIMIT = 50
_MAX_LIST_LIMIT = 100


@dataclass(frozen=True)
class AssignmentCatalogDeps:
    data_dir: Path
    app_root: Path
    load_assignment_meta: Callable[[Path], Dict[str, Any]]
    load_assignment_requirements: Callable[[Path], Dict[str, Any]]
    count_csv_rows: Callable[[Path], int]
    sanitize_filename: Callable[[str], str]


@dataclass(frozen=True)
class AssignmentMetaPostprocessDeps:
    data_dir: Path
    discussion_complete_marker: str
    load_profile_file: Callable[[Path], Dict[str, Any]]
    parse_ids_value: Callable[[Any], List[str]]
    resolve_scope: Callable[[str, List[str], str], str]
    normalize_due_at: Callable[[Any], str]
    compute_expected_students: Callable[[str, str, List[str]], List[str]]
    atomic_write_json: Callable[[Path, Any], None]
    now_iso: Callable[[], str]


def _resolve_assignment_dir(data_dir: Path, assignment_id: str) -> Optional[Path]:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        return None
    target = (root / aid).resolve()
    if target != root and root not in target.parents:
        return None
    return target


def resolve_assignment_date(meta: Dict[str, Any], folder: Path) -> Optional[str]:
    date_val = meta.get("date")
    if date_val:
        return date_val
    raw = meta.get("assignment_id") or folder.name
    import re
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(raw))
    if match:
        return match.group(0)
    return None


def assignment_specificity(meta: Dict[str, Any], student_id: Optional[str], class_name: Optional[str]) -> int:
    scope = meta.get("scope")
    student_ids = meta.get("student_ids") or []
    class_meta = meta.get("class_name")

    if scope == "student":
        return 3 if student_id and student_id in student_ids else 0
    if scope == "class":
        return 2 if class_name and class_meta and class_name == class_meta else 0
    if scope == "public":
        return 1

    if student_ids:
        return 3 if student_id and student_id in student_ids else 0
    if class_name and class_meta and class_name == class_meta:
        return 2
    return 1


def parse_iso_timestamp(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return 0.0


def _normalize_paging(limit: Any, cursor: Any) -> tuple[int, int]:
    try:
        limit_int = int(limit)
    except Exception:
        limit_int = _DEFAULT_LIST_LIMIT
    try:
        cursor_int = int(cursor)
    except Exception:
        cursor_int = 0
    if limit_int <= 0:
        limit_int = _DEFAULT_LIST_LIMIT
    limit_int = min(limit_int, _MAX_LIST_LIMIT)
    cursor_int = max(0, cursor_int)
    return limit_int, cursor_int


def list_assignments(*, limit: Any = _DEFAULT_LIST_LIMIT, cursor: Any = 0, deps: AssignmentCatalogDeps) -> Dict[str, Any]:
    limit_int, cursor_int = _normalize_paging(limit, cursor)
    assignments_dir = deps.data_dir / "assignments"
    if not assignments_dir.exists():
        return {
            "assignments": [],
            "total": 0,
            "limit": limit_int,
            "cursor": cursor_int,
            "has_more": False,
        }

    items = []
    for folder in assignments_dir.iterdir():
        if not folder.is_dir():
            continue
        assignment_id = folder.name
        meta = deps.load_assignment_meta(folder)
        assignment_date = resolve_assignment_date(meta, folder)
        questions_path = folder / "questions.csv"
        count = deps.count_csv_rows(questions_path) if questions_path.exists() else 0
        updated_at = None
        if meta.get("generated_at"):
            updated_at = meta.get("generated_at")
        elif questions_path.exists():
            updated_at = datetime.fromtimestamp(questions_path.stat().st_mtime).isoformat(timespec="seconds")
        items.append(
            {
                "assignment_id": assignment_id,
                "date": assignment_date,
                "question_count": count,
                "updated_at": updated_at,
                "mode": meta.get("mode"),
                "target_kp": meta.get("target_kp") or [],
                "class_name": meta.get("class_name"),
            }
        )

    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    total = len(items)
    page = items[cursor_int : cursor_int + limit_int]
    next_cursor = cursor_int + len(page)
    return {
        "assignments": page,
        "total": total,
        "limit": limit_int,
        "cursor": cursor_int,
        "next_cursor": next_cursor if next_cursor < total else None,
        "has_more": next_cursor < total,
    }


def find_assignment_for_date(
    *,
    date_str: str,
    student_id: Optional[str],
    class_name: Optional[str],
    deps: AssignmentCatalogDeps,
) -> Optional[Dict[str, Any]]:
    assignments_dir = deps.data_dir / "assignments"
    if not assignments_dir.exists():
        return None

    candidates = []
    for folder in assignments_dir.iterdir():
        if not folder.is_dir():
            continue
        meta = deps.load_assignment_meta(folder)
        assignment_date = resolve_assignment_date(meta, folder)
        if assignment_date != date_str:
            continue
        spec = assignment_specificity(meta, student_id, class_name)
        if spec <= 0:
            continue
        source = str(meta.get("source") or "").lower()
        teacher_flag = 0 if source == "auto" else 1
        updated_at = meta.get("generated_at")
        if not updated_at:
            questions_path = folder / "questions.csv"
            if questions_path.exists():
                updated_at = datetime.fromtimestamp(questions_path.stat().st_mtime).isoformat(timespec="seconds")
        candidates.append((teacher_flag, spec, parse_iso_timestamp(updated_at), folder, meta))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    best = candidates[0]
    return {"folder": best[3], "meta": best[4]}


def read_text_safe(path: Path, limit: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def build_assignment_detail(
    *,
    folder: Path,
    include_text: bool,
    deps: AssignmentCatalogDeps,
) -> Dict[str, Any]:
    meta = deps.load_assignment_meta(folder)
    requirements = deps.load_assignment_requirements(folder)
    assignment_id = meta.get("assignment_id") or folder.name
    assignment_date = resolve_assignment_date(meta, folder)
    questions_path = folder / "questions.csv"

    questions: List[Dict[str, Any]] = []
    if questions_path.exists():
        with questions_path.open(encoding="utf-8") as file_handle:
            reader = csv.DictReader(file_handle)
            for row in reader:
                item = dict(row)
                stem_ref = item.get("stem_ref") or ""
                if include_text and stem_ref:
                    stem_path = Path(stem_ref)
                    if not stem_path.is_absolute():
                        stem_path = deps.app_root / stem_path
                    item["stem_text"] = read_text_safe(stem_path)
                questions.append(item)

    delivery = None
    source_files = meta.get("source_files") or []
    if meta.get("delivery_mode") and source_files:
        delivery_files = []
        for fname in source_files:
            safe_name = deps.sanitize_filename(str(fname))
            if not safe_name:
                continue
            delivery_files.append(
                {
                    "name": safe_name,
                    "url": f"/assignment/{assignment_id}/download?file={quote(safe_name)}",
                }
            )
        delivery = {"mode": meta.get("delivery_mode"), "files": delivery_files}

    return {
        "assignment_id": assignment_id,
        "date": assignment_date,
        "meta": meta,
        "requirements": requirements,
        "question_count": len(questions),
        "questions": questions if include_text else None,
        "delivery": delivery,
    }


def postprocess_assignment_meta(
    *,
    assignment_id: str,
    due_at: Optional[str],
    expected_students: Optional[List[str]],
    completion_policy: Optional[Dict[str, Any]],
    deps: AssignmentMetaPostprocessDeps,
) -> None:
    folder = _resolve_assignment_dir(deps.data_dir, assignment_id)
    if folder is None:
        return
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        return

    meta = deps.load_profile_file(meta_path)
    if not isinstance(meta, dict):
        meta = {}

    student_ids = deps.parse_ids_value(meta.get("student_ids") or [])
    class_name = str(meta.get("class_name") or "")
    scope_val = deps.resolve_scope(str(meta.get("scope") or ""), student_ids, class_name)

    due_norm = deps.normalize_due_at(due_at) if due_at is not None else deps.normalize_due_at(meta.get("due_at"))
    if due_at is not None:
        meta["due_at"] = due_norm or ""
    elif due_norm:
        meta["due_at"] = due_norm

    exp: List[str]
    if expected_students is not None:
        exp = [str(s).strip() for s in expected_students if str(s).strip()]
    else:
        raw = meta.get("expected_students")
        if isinstance(raw, list):
            exp = [str(s).strip() for s in raw if str(s).strip()]
        else:
            exp = []

    if not exp and expected_students is None:
        exp = deps.compute_expected_students(scope_val, class_name, student_ids)

    if exp:
        meta["expected_students"] = exp
        meta.setdefault("expected_students_generated_at", deps.now_iso())

    meta["scope"] = scope_val

    if completion_policy is None:
        completion_policy = {
            "requires_discussion": True,
            "discussion_marker": deps.discussion_complete_marker,
            "requires_submission": True,
            "min_graded_total": 1,
            "best_attempt": "score_earned_then_correct_then_graded_total",
            "version": 1,
        }
    meta.setdefault("completion_policy", completion_policy)

    deps.atomic_write_json(meta_path, meta)
