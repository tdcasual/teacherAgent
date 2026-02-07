from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class AssignmentGenerateError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class AssignmentGenerateDeps:
    app_root: Path
    parse_date_str: Callable[[Optional[str]], str]
    ensure_requirements_for_assignment: Callable[[str, str, Optional[Dict[str, Any]], str], Optional[Dict[str, Any]]]
    run_script: Callable[[list[str]], str]
    postprocess_assignment_meta: Callable[..., Any]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]


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
    deps: AssignmentGenerateDeps,
) -> Dict[str, Any]:
    script = deps.app_root / "skills" / "physics-student-coach" / "scripts" / "select_practice.py"

    requirements_payload = None
    if requirements_json:
        try:
            requirements_payload = json.loads(requirements_json)
        except Exception:
            raise AssignmentGenerateError(400, "requirements_json is not valid JSON")

    date_str = deps.parse_date_str(date)
    req_result = deps.ensure_requirements_for_assignment(
        assignment_id,
        date_str,
        requirements_payload,
        str(source or "teacher"),
    )
    if req_result and req_result.get("error"):
        raise AssignmentGenerateError(400, req_result)

    args = [
        "python3",
        str(script),
        "--assignment-id",
        assignment_id,
        "--per-kp",
        str(per_kp),
    ]
    if kp:
        args += ["--kp", kp]
    if question_ids:
        args += ["--question-ids", question_ids]
    if mode:
        args += ["--mode", mode]
    if date:
        args += ["--date", date]
    if class_name:
        args += ["--class-name", class_name]
    if student_ids:
        args += ["--student-ids", student_ids]
    if source:
        args += ["--source", source]
    if core_examples:
        args += ["--core-examples", core_examples]
    if generate:
        args += ["--generate"]

    out = deps.run_script(args)

    try:
        deps.postprocess_assignment_meta(assignment_id, due_at=due_at or None)
    except Exception as exc:
        deps.diag_log(
            "assignment.meta.postprocess_failed",
            {"assignment_id": assignment_id, "error": str(exc)[:200]},
        )

    return {"ok": True, "output": out}
