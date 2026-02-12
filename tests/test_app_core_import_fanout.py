"""Import fan-out guardrails for app_core compatibility facade."""

import ast
from pathlib import Path

_APP_CORE_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "app_core.py"
)


def test_app_core_import_fanout_budget() -> None:
    tree = ast.parse(_APP_CORE_PATH.read_text(encoding="utf-8"))
    top_level_imports = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]
    assert len(top_level_imports) <= 150, (
        f"app_core.py has {len(top_level_imports)} top-level import statements (limit 150). "
        "Move domain wrappers/imports to context facades."
    )

    relative_modules = {
        (node.level, node.module)
        for node in top_level_imports
        if isinstance(node, ast.ImportFrom) and node.level > 0 and node.module
    }
    assert len(relative_modules) <= 90, (
        f"app_core.py references {len(relative_modules)} distinct relative modules (limit 90). "
        "Consolidate imports via context facades or wiring modules."
    )
