from __future__ import annotations

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


@dataclass(frozen=True)
class AssignmentGenerateToolDeps:
    app_root: Path
    optional_assignment_date: Callable[[Optional[str]], Optional[str]]
    ensure_requirements_for_assignment: Callable[
        [str, str, Optional[Dict[str, Any]], str], Optional[Dict[str, Any]]
    ]
    run_script: Callable[[list[str]], str]
    postprocess_assignment_meta: Callable[..., None]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]


def _validate_assignment_requirements(
    args: Dict[str, Any],
    deps: AssignmentGenerateToolDeps,
) -> Optional[Dict[str, Any]]:
    if args.get("skip_validation"):
        return None
    assignment_id = str(args.get("assignment_id", ""))
    try:
        date_str = str(deps.optional_assignment_date(args.get("date")) or "")
    except InvalidAssignmentDate:
        return {"error": "invalid_assignment_date"}
    source = str(args.get("source") or "teacher")
    requirements_payload = args.get("requirements")
    return deps.ensure_requirements_for_assignment(
        assignment_id, date_str, requirements_payload, source
    )


def _tool_owner_fields(args: Dict[str, Any]) -> Dict[str, str]:
    teacher_id = str(getattr(get_current_principal(), "actor_id", "") or "").strip()
    subject_id = str(args.get("subject_id") or "").strip()
    if not teacher_id:
        return {"error": "teacher_id_required"}
    if not subject_id:
        return {"error": "subject_id_required"}
    return {"teacher_id": teacher_id, "subject_id": subject_id}


def _tool_assignment_date(
    args: Dict[str, Any], deps: AssignmentGenerateToolDeps
) -> str | Dict[str, str]:
    try:
        return str(deps.optional_assignment_date(args.get("date")) or "")
    except InvalidAssignmentDate:
        return {"error": "invalid_assignment_date"}


def assignment_generate(args: Dict[str, Any], deps: AssignmentGenerateToolDeps) -> Dict[str, Any]:
    assignment_id = str(args.get("assignment_id", ""))
    req_result = _validate_assignment_requirements(args, deps)
    if req_result and req_result.get("error"):
        return req_result
    owner = _tool_owner_fields(args)
    if owner.get("error"):
        return owner
    date_str = _tool_assignment_date(args, deps)
    if isinstance(date_str, dict):
        return date_str

    cmd = [
        "python3",
        str(assignment_generate_script(deps.app_root)),
        "--assignment-id",
        assignment_id,
    ]
    append_assignment_generate_options(
        cmd,
        (
            ("--kp", str(args.get("kp", "") or "")),
            ("--question-ids", args.get("question_ids")),
            ("--mode", args.get("mode")),
            ("--date", date_str),
            ("--class-name", args.get("class_name")),
            ("--student-ids", args.get("student_ids")),
            ("--source", args.get("source")),
            ("--per-kp", args.get("per_kp")),
            ("--core-examples", args.get("core_examples")),
            ("--teacher-id", owner["teacher_id"]),
            ("--subject-id", owner["subject_id"]),
            ("--due-at", args.get("due_at")),
            ("--visibility-status", DRAFT_VISIBILITY_STATUS),
        ),
    )
    append_assignment_generate_flag(
        cmd,
        flag="--generate",
        enabled=bool(args.get("generate")),
    )

    out = deps.run_script(cmd)
    try_postprocess_assignment_meta(
        assignment_id=assignment_id,
        due_at=args.get("due_at"),
        postprocess_assignment_meta=deps.postprocess_assignment_meta,
        diag_log=deps.diag_log,
        visibility_status=DRAFT_VISIBILITY_STATUS,
        teacher_id=owner["teacher_id"],
        subject_id=owner["subject_id"],
        completion_policy=generated_assignment_completion_policy(),
    )

    return {"ok": True, "output": out, "assignment_id": args.get("assignment_id")}


def assignment_render(args: Dict[str, Any], deps: AssignmentGenerateToolDeps) -> Dict[str, Any]:
    from .core_utils import _resolve_app_path

    script = deps.app_root / "scripts" / "render_assignment_pdf.py"
    assignment_id = str(args.get("assignment_id", ""))
    cmd = ["python3", str(script), "--assignment-id", assignment_id]
    if args.get("assignment_questions"):
        p = _resolve_app_path(args.get("assignment_questions"), must_exist=True)
        if not p:
            return {"error": "assignment_questions_not_found_or_outside_app_root"}
        cmd += ["--assignment-questions", str(p)]
    out_pdf = None
    if args.get("out"):
        p = _resolve_app_path(args.get("out"), must_exist=False)
        if not p:
            return {"error": "out_outside_app_root"}
        out_pdf = p
        cmd += ["--out", str(p)]
    out = deps.run_script(cmd)
    pdf_path = str(out_pdf) if out_pdf else f"output/pdf/assignment_{assignment_id}.pdf"
    return {"ok": True, "output": out, "pdf": pdf_path}
