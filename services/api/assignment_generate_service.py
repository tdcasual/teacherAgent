from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .assignment_generate_cli_service import (
    DRAFT_VISIBILITY_STATUS,
    append_assignment_generate_flag,
    append_assignment_generate_options,
    assignment_generate_script,
    generated_assignment_completion_policy,
    try_postprocess_assignment_meta,
)
from .auth_service import get_current_principal
from .paths import InvalidAssignmentDate


class AssignmentGenerateError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class AssignmentGenerateDeps:
    app_root: Path
    optional_assignment_date: Callable[[Optional[str]], Optional[str]]
    ensure_requirements_for_assignment: Callable[
        [str, str, Optional[Dict[str, Any]], str], Optional[Dict[str, Any]]
    ]
    run_script: Callable[[list[str]], str]
    postprocess_assignment_meta: Callable[..., Any]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]


def _parse_requirements_json(requirements_json: Optional[str]) -> Optional[Dict[str, Any]]:
    if not requirements_json:
        return None
    try:
        return json.loads(requirements_json)
    except Exception:
        raise AssignmentGenerateError(400, "requirements_json is not valid JSON")


def _require_generate_owner(*, subject_id: Optional[str]) -> tuple[str, str]:
    teacher_id = str(getattr(get_current_principal(), "actor_id", "") or "").strip()
    subject_val = str(subject_id or "").strip()
    if not teacher_id:
        raise AssignmentGenerateError(400, "teacher_id_required")
    if not subject_val:
        raise AssignmentGenerateError(400, "subject_id_required")
    return teacher_id, subject_val


def _generate_assignment_date(date: Optional[str], deps: AssignmentGenerateDeps) -> str:
    try:
        return str(deps.optional_assignment_date(date) or "")
    except InvalidAssignmentDate as exc:
        raise AssignmentGenerateError(400, "invalid_assignment_date") from exc


def _ensure_assignment_requirements(
    *,
    assignment_id: str,
    date_str: str,
    requirements_payload: Optional[Dict[str, Any]],
    source: Optional[str],
    deps: AssignmentGenerateDeps,
) -> None:
    req_result = deps.ensure_requirements_for_assignment(
        assignment_id,
        date_str,
        requirements_payload,
        str(source or "teacher"),
    )
    if req_result and req_result.get("error"):
        raise AssignmentGenerateError(400, req_result)


def generate_assignment(
    *,
    assignment_id: str,
    kp: str,
    question_ids: Optional[str],
    per_kp: int,
    core_examples: Optional[str],
    generate: bool,
    mode: Optional[str],
    date: Optional[str],
    due_at: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    source: Optional[str],
    requirements_json: Optional[str],
    subject_id: Optional[str] = None,
    deps: AssignmentGenerateDeps,
) -> Dict[str, Any]:
    requirements_payload = _parse_requirements_json(requirements_json)
    teacher_id, subject_val = _require_generate_owner(subject_id=subject_id)
    date_str = _generate_assignment_date(date, deps)
    _ensure_assignment_requirements(
        assignment_id=assignment_id,
        date_str=date_str,
        requirements_payload=requirements_payload,
        source=source,
        deps=deps,
    )

    args = [
        "python3",
        str(assignment_generate_script(deps.app_root)),
        "--assignment-id",
        assignment_id,
        "--per-kp",
        str(per_kp),
    ]
    append_assignment_generate_options(
        args,
        (
            ("--kp", kp),
            ("--question-ids", question_ids),
            ("--mode", mode),
            ("--date", date_str),
            ("--class-name", class_name),
            ("--student-ids", student_ids),
            ("--source", source),
            ("--core-examples", core_examples),
            ("--teacher-id", teacher_id),
            ("--subject-id", subject_val),
            ("--due-at", due_at),
            ("--visibility-status", DRAFT_VISIBILITY_STATUS),
        ),
    )
    append_assignment_generate_flag(args, flag="--generate", enabled=generate)

    out = deps.run_script(args)
    try_postprocess_assignment_meta(
        assignment_id=assignment_id,
        due_at=due_at,
        postprocess_assignment_meta=deps.postprocess_assignment_meta,
        diag_log=deps.diag_log,
        visibility_status=DRAFT_VISIBILITY_STATUS,
        teacher_id=teacher_id,
        subject_id=subject_val,
        completion_policy=generated_assignment_completion_policy(),
    )

    return {"ok": True, "output": out}
