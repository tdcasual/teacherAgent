"""Maintainability guardrails for assignment upload confirm orchestration."""

import ast
from pathlib import Path

_SERVICE_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "assignment_upload_confirm_service.py"
)


def test_confirm_assignment_upload_line_budget() -> None:
    source = _SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "confirm_assignment_upload"
        ):
            target = node
            break
    assert target is not None, "confirm_assignment_upload not found"
    lines = target.end_lineno - target.lineno + 1
    assert lines < 130, (
        f"confirm_assignment_upload is {lines} lines (limit 130). "
        "Split orchestration into private helper functions."
    )
