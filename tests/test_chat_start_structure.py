"""Maintainability guardrails for chat start orchestration."""

import ast
from pathlib import Path

_SERVICE_PATH = (
    Path(__file__).resolve().parent.parent / "services" / "api" / "chat_start_service.py"
)


def test_start_chat_orchestration_line_budget() -> None:
    source = _SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "start_chat_orchestration"
        ):
            target = node
            break
    assert target is not None, "start_chat_orchestration not found"
    lines = target.end_lineno - target.lineno + 1
    assert lines < 150, (
        f"start_chat_orchestration is {lines} lines (limit 150). "
        "Split orchestration into private helper functions."
    )
