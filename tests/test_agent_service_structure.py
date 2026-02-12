"""Maintainability guardrails for agent runtime orchestration."""

import ast
from pathlib import Path

_SERVICE_PATH = Path(__file__).resolve().parent.parent / "services" / "api" / "agent_service.py"


def test_run_agent_runtime_line_budget() -> None:
    source = _SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    target = None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "run_agent_runtime"
        ):
            target = node
            break
    assert target is not None, "run_agent_runtime not found"
    lines = target.end_lineno - target.lineno + 1
    assert lines < 170, (
        f"run_agent_runtime is {lines} lines (limit 170). "
        "Split runtime flow into private helper functions."
    )
