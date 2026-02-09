from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class AssignmentGenerateToolDeps:
    app_root: Path
    parse_date_str: Callable[[Optional[str]], str]
    ensure_requirements_for_assignment: Callable[[str, str, Optional[Dict[str, Any]], str], Optional[Dict[str, Any]]]
    run_script: Callable[[list[str]], str]
    postprocess_assignment_meta: Callable[..., None]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]


def assignment_generate(args: Dict[str, Any], deps: AssignmentGenerateToolDeps) -> Dict[str, Any]:
    script = deps.app_root / "skills" / "physics-student-coach" / "scripts" / "select_practice.py"
    assignment_id = str(args.get("assignment_id", ""))
    date_str = deps.parse_date_str(args.get("date"))
    source = str(args.get("source") or "teacher")
    requirements_payload = args.get("requirements")

    if not args.get("skip_validation"):
        req_result = deps.ensure_requirements_for_assignment(assignment_id, date_str, requirements_payload, source)
        if req_result and req_result.get("error"):
            return req_result

    kp_value = str(args.get("kp", "") or "")
    cmd = ["python3", str(script), "--assignment-id", assignment_id]
    if kp_value:
        cmd += ["--kp", kp_value]

    question_ids = args.get("question_ids")
    if question_ids:
        cmd += ["--question-ids", str(question_ids)]

    mode = args.get("mode")
    if mode:
        cmd += ["--mode", str(mode)]

    date_val = args.get("date")
    if date_val:
        cmd += ["--date", str(date_val)]

    class_name = args.get("class_name")
    if class_name:
        cmd += ["--class-name", str(class_name)]

    student_ids = args.get("student_ids")
    if student_ids:
        cmd += ["--student-ids", str(student_ids)]

    source_val = args.get("source")
    if source_val:
        cmd += ["--source", str(source_val)]

    per_kp = args.get("per_kp")
    if per_kp is not None:
        cmd += ["--per-kp", str(per_kp)]

    if args.get("core_examples"):
        cmd += ["--core-examples", str(args.get("core_examples"))]

    if args.get("generate"):
        cmd += ["--generate"]

    out = deps.run_script(cmd)

    try:
        deps.postprocess_assignment_meta(assignment_id, due_at=args.get("due_at"))
    except Exception as exc:
        deps.diag_log(
            "assignment.meta.postprocess_failed",
            {"assignment_id": assignment_id, "error": str(exc)[:200]},
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
