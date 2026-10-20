from __future__ import annotations

from typing import Any, Dict

from .assignment_generate_service import (
    AssignmentGenerateDeps,
    AssignmentGenerateError,
    generate_assignment,
)

AssignmentGenerateToolDeps = AssignmentGenerateDeps


def assignment_generate(args: Dict[str, Any], deps: AssignmentGenerateDeps) -> Dict[str, Any]:
    generate_flag = args.get("generate", True)
    if generate_flag is None:
        generate_flag = True
    requirements = args.get("requirements")
    requirements_json = None
    if isinstance(requirements, dict):
        import json as _json

        requirements_json = _json.dumps(requirements, ensure_ascii=False)
    try:
        per_kp_raw = args.get("per_kp", 5)
        per_kp = int(per_kp_raw) if per_kp_raw not in (None, "") else 5
    except (TypeError, ValueError):
        per_kp = 5
    try:
        result = generate_assignment(
            assignment_id=str(args.get("assignment_id", "") or ""),
            kp=str(args.get("kp", "") or ""),
            question_ids=args.get("question_ids"),
            per_kp=per_kp,
            core_examples=args.get("core_examples"),
            generate=bool(generate_flag),
            mode=args.get("mode"),
            date=args.get("date"),
            due_at=args.get("due_at"),
            class_name=args.get("class_name"),
            student_ids=args.get("student_ids"),
            source=args.get("source"),
            requirements_json=requirements_json,
            subject_id=args.get("subject_id"),
            assignment_kind=args.get("assignment_kind"),
            content_source=args.get("content_source"),
            seed=args.get("seed"),
            skip_validation=bool(args.get("skip_validation")),
            deps=deps,
        )
    except AssignmentGenerateError as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            return detail
        return {"error": detail}
    result.setdefault("assignment_id", args.get("assignment_id"))
    return result


def assignment_render(args: Dict[str, Any], deps: AssignmentGenerateDeps) -> Dict[str, Any]:
    from .config import DATA_DIR
    from .core_utils import _resolve_app_path, _resolve_data_dir_path

    script = deps.app_root / "scripts" / "render_assignment_pdf.py"
    assignment_id = str(args.get("assignment_id", ""))
    cmd = [
        "python3",
        str(script),
        "--assignment-id",
        assignment_id,
        "--data-dir",
        str(DATA_DIR),
        "--app-root",
        str(deps.app_root),
    ]
    if args.get("assignment_questions"):
        p = _resolve_app_path(args.get("assignment_questions"), must_exist=True)
        if not p:
            return {"error": "assignment_questions_not_found_or_outside_app_root"}
        cmd += ["--assignment-questions", str(p)]
    out_pdf = None
    if args.get("out"):
        p = _resolve_data_dir_path(args.get("out"), must_exist=False)
        if not p:
            return {"error": "out_outside_data_dir"}
        out_pdf = p
        cmd += ["--out", str(p)]
    out = deps.run_script(cmd)
    pdf_path = str(out_pdf) if out_pdf else f"output/pdf/assignment_{assignment_id}.pdf"
    return {"ok": True, "output": out, "pdf": pdf_path}
