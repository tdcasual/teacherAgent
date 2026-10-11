from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .assignment.store import connect as assignment_connect
from .assignment.store import ensure as assignment_ensure
from .assignment.store import get_assignment as assignment_get
from .assignment.visibility import effective_visibility_status
from .assignment_generate_cli_service import (
    DRAFT_VISIBILITY_STATUS,
    generated_assignment_completion_policy,
    try_postprocess_assignment_meta,
)
from .auth_service import get_current_principal
from .paths import APP_ROOT, DATA_DIR, InvalidAssignmentDate, optional_assignment_date
from .question_bank_select_service import (
    load_recent_assignments,
    parse_kp_list,
    pick_practice_items,
    read_question_bank,
    write_questions_csv,
)

_log = logging.getLogger(__name__)


class AssignmentDraftFromBankError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class AssignmentDraftFromBankDeps:
    data_dir: Path
    app_root: Path
    optional_assignment_date: Callable[[Optional[str]], Optional[str]]
    parse_ids_value: Callable[[Any], list]
    resolve_scope: Callable[[str, list, str], str]
    normalize_due_at: Callable[[Any], Optional[str]]
    postprocess_assignment_meta: Callable[..., Any]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]
    now_iso: Callable[[], str]


def _resolve_assignment_dir(data_dir: Path, assignment_id: str) -> Path:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise AssignmentDraftFromBankError(400, "assignment_id is required")
    target = (root / aid).resolve()
    if target != root and root not in target.parents:
        raise AssignmentDraftFromBankError(400, "invalid assignment_id")
    return target


def _require_owner(*, subject_id: Optional[str]) -> tuple[str, str]:
    teacher_id = str(getattr(get_current_principal(), "actor_id", "") or "").strip()
    subject_val = str(subject_id or "").strip()
    if not teacher_id:
        raise AssignmentDraftFromBankError(400, "teacher_id_required")
    if not subject_val:
        raise AssignmentDraftFromBankError(400, "subject_id_required")
    return teacher_id, subject_val


def _clamp_count(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 5
    return max(1, min(20, value))


def _conflict_if_not_own_draft(
    *,
    out_dir: Path,
    assignment_id: str,
    teacher_id: str,
    data_dir: Path,
) -> None:
    meta: Dict[str, Any] = {}
    meta_path = out_dir / "meta.json"
    if meta_path.exists():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            meta = loaded
    exists = out_dir.exists() and any(out_dir.iterdir()) if out_dir.exists() else False
    conn = assignment_connect(data_dir)
    try:
        assignment_ensure(conn, data_dir=data_dir)
        sql_row = assignment_get(conn, assignment_id)
    finally:
        conn.close()
    if not exists and sql_row is None:
        return
    owner = str(meta.get("teacher_id") or "").strip()
    vis = effective_visibility_status(meta)
    if vis == "draft" and owner == teacher_id:
        return
    raise AssignmentDraftFromBankError(409, "assignment already exists")


def create_assignment_draft_from_bank(
    *,
    assignment_id: str,
    subject_id: Optional[str],
    kp: str = "",
    count: Any = 5,
    date: Optional[str] = None,
    due_at: Optional[str] = None,
    class_name: Optional[str] = None,
    student_ids: Optional[str] = None,
    deps: AssignmentDraftFromBankDeps,
) -> Dict[str, Any]:
    teacher_id, subject_val = _require_owner(subject_id=subject_id)
    try:
        date_str = str(deps.optional_assignment_date(date) or "")
    except InvalidAssignmentDate as exc:
        raise AssignmentDraftFromBankError(400, "invalid_assignment_date") from exc
    out_dir = _resolve_assignment_dir(deps.data_dir, assignment_id)
    _conflict_if_not_own_draft(
        out_dir=out_dir,
        assignment_id=assignment_id,
        teacher_id=teacher_id,
        data_dir=deps.data_dir,
    )
    excluded = load_recent_assignments(deps.data_dir / "assignments", 14)
    existing_csv = out_dir / "questions.csv"
    if existing_csv.exists():
        excluded -= {
            str(row.get("question_id") or "")
            for row in read_question_bank(existing_csv)
            if row.get("question_id")
        }
    picked = pick_practice_items(
        data_dir=deps.data_dir,
        app_root=deps.app_root,
        kp_list=parse_kp_list(kp),
        excluded_ids=excluded,
        count=_clamp_count(count),
    )
    if not picked.get("ok"):
        deps.diag_log(
            "assignment.draft.from_bank",
            {"assignment_id": assignment_id, "ok": False, "reason": "question_bank_insufficient"},
        )
        raise AssignmentDraftFromBankError(409, "question_bank_insufficient")
    items = list(picked.get("items") or [])
    out_dir.mkdir(parents=True, exist_ok=True)
    write_questions_csv(out_dir / "questions.csv", items)
    student_ids_list = deps.parse_ids_value(student_ids)
    scope_val = deps.resolve_scope("", student_ids_list, str(class_name or ""))
    existing_req = {}
    req_path = out_dir / "requirements.json"
    if req_path.exists():
        try:
            loaded = json.loads(req_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            existing_req = loaded
    meta = {
        "assignment_id": assignment_id,
        "teacher_id": teacher_id,
        "subject_id": subject_val,
        "pack_id": subject_val,
        "date": date_str,
        "due_at": deps.normalize_due_at(due_at) or "",
        "visibility_status": DRAFT_VISIBILITY_STATUS,
        "archived_at": None,
        "mode": "kp",
        "content_source": "bank",
        "assignment_kind": "problem_set",
        "target_kp": [str(item.get("kp_id") or "") for item in items if item.get("kp_id")],
        "question_ids": [str(item.get("question_id") or "") for item in items if item.get("question_id")],
        "class_name": class_name or "",
        "student_ids": student_ids_list,
        "scope": scope_val,
        "source": "teacher",
        "generated_at": deps.now_iso(),
        "completion_policy": generated_assignment_completion_policy(
            assignment_kind="problem_set"
        ),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try_postprocess_assignment_meta(
        assignment_id=assignment_id,
        due_at=due_at,
        postprocess_assignment_meta=deps.postprocess_assignment_meta,
        diag_log=deps.diag_log,
        visibility_status=DRAFT_VISIBILITY_STATUS,
        teacher_id=teacher_id,
        subject_id=subject_val,
        completion_policy=generated_assignment_completion_policy(
            assignment_kind="problem_set"
        ),
        content_source="bank",
        assignment_kind="problem_set",
    )
    deps.diag_log(
        "assignment.draft.from_bank",
        {"assignment_id": assignment_id, "kind": "problem_set", "source": "bank", "ok": True},
    )
    return {
        "ok": True,
        "assignment_id": assignment_id,
        "draft": {
            "assignment_id": assignment_id,
            "requirements": existing_req,
            "questions": items,
            "requirements_missing": [],
            "assignment_kind": "problem_set",
            "content_source": "bank",
            "question_count": len(items),
        },
    }


def build_default_from_bank_deps() -> AssignmentDraftFromBankDeps:
    from datetime import datetime

    from .core_services_application import postprocess_assignment_meta
    from .core_utils import normalize_due_at, parse_ids_value, resolve_scope

    return AssignmentDraftFromBankDeps(
        data_dir=DATA_DIR,
        app_root=APP_ROOT,
        optional_assignment_date=optional_assignment_date,
        parse_ids_value=parse_ids_value,
        resolve_scope=resolve_scope,
        normalize_due_at=normalize_due_at,
        postprocess_assignment_meta=postprocess_assignment_meta,
        diag_log=lambda event, payload=None: _log.info("%s %s", event, payload or {}),
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )
