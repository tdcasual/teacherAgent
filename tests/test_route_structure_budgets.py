"""Centralized maintainability budgets for route build_router composition."""

import ast
from pathlib import Path

_ROUTES_DIR = Path(__file__).resolve().parent.parent / "services" / "api" / "routes"
_BUILD_ROUTER_BUDGETS = {
    "assignment_routes.py": 60,
    "chat_routes.py": 20,
    "exam_routes.py": 60,
    "misc_routes.py": 30,
    "skill_routes.py": 35,
    "student_routes.py": 60,
    "teacher_routes.py": 50,
}


def _build_router_line_count(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_router":
            return node.end_lineno - node.lineno + 1
    raise AssertionError(f"build_router not found in {path.name}")


def test_build_router_budget_coverage() -> None:
    discovered = set()
    for path in _ROUTES_DIR.glob("*_routes.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        has_build_router = any(
            isinstance(node, ast.FunctionDef) and node.name == "build_router"
            for node in ast.walk(tree)
        )
        if has_build_router:
            discovered.add(path.name)
    assert discovered == set(
        _BUILD_ROUTER_BUDGETS.keys()
    ), "Route budget map must cover every *_routes.py module exposing build_router."


def test_build_router_line_budgets() -> None:
    for file_name, budget in sorted(_BUILD_ROUTER_BUDGETS.items()):
        path = _ROUTES_DIR / file_name
        lines = _build_router_line_count(path)
        assert lines < budget, (
            f"{file_name}: build_router is {lines} lines (limit {budget}). "
            "Keep route modules as thin composition layers."
        )
