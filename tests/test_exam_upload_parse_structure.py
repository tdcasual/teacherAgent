"""Maintainability guardrails for exam upload parse orchestration."""

import ast
from pathlib import Path

_SERVICE_PATH = (
    Path(__file__).resolve().parent.parent / "services" / "api" / "exam_upload_parse_service.py"
)


def test_process_exam_upload_job_line_budget() -> None:
    source = _SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "process_exam_upload_job"
        ):
            target = node
            break
    assert target is not None, "process_exam_upload_job not found"
    lines = target.end_lineno - target.lineno + 1
    assert lines < 220, (
        f"process_exam_upload_job is {lines} lines (limit 220). "
        "Split more orchestration into private helper functions."
    )
