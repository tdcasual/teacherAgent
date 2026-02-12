"""Maintainability guardrails for chat job processing orchestration."""

import ast
from pathlib import Path

_SERVICE_PATH = (
    Path(__file__).resolve().parent.parent / "services" / "api" / "chat_job_processing_service.py"
)


def test_process_chat_job_line_budget() -> None:
    source = _SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "process_chat_job"
        ):
            target = node
            break
    assert target is not None, "process_chat_job not found"
    lines = target.end_lineno - target.lineno + 1
    assert lines < 190, (
        f"process_chat_job is {lines} lines (limit 190). "
        "Split orchestration into private helper functions."
    )
