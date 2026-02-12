"""Maintainability guardrails for assignment upload parse orchestration."""

import ast
from pathlib import Path

_SERVICE_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "assignment_upload_parse_service.py"
)


def test_process_upload_job_line_budget() -> None:
    source = _SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "process_upload_job"
        ):
            target = node
            break
    assert target is not None, "process_upload_job not found"
    lines = target.end_lineno - target.lineno + 1
    assert lines < 130, (
        f"process_upload_job is {lines} lines (limit 130). "
        "Split orchestration into private helper functions."
    )
