"""Guard tests to prevent app_core.py from regressing into a God Object.

After decomposition, app_core.py should remain a thin composition root:
- Re-exports from extracted modules (config, paths, repositories, wiring)
- Thin wrapper functions that delegate to _impl + _deps()
- Module-level state initialization (locks, queues, LLM_GATEWAY)

Original: 4,278 lines.  After decomposition: ~1,830 lines.
"""
import ast
from pathlib import Path


_APP_CORE_PATH = Path(__file__).resolve().parent.parent / "services" / "api" / "app_core.py"


def test_app_core_line_count():
    """app_core.py should stay under 2000 lines after decomposition."""
    source = _APP_CORE_PATH.read_text(encoding="utf-8")
    line_count = len(source.splitlines())
    assert line_count < 1400, (
        f"app_core.py is {line_count} lines (limit 1400). "
        "Extract new logic to domain modules instead of adding to app_core."
    )


def test_app_core_no_long_functions():
    """No function in app_core.py should exceed 35 lines.

    Wrapper functions should be short delegations. If a function is long,
    it contains business logic that belongs in a service module.
    """
    source = _APP_CORE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_lines = node.end_lineno - node.lineno + 1
            if body_lines > 35:
                violations.append(f"{node.name} ({body_lines} lines, line {node.lineno})")
    assert not violations, (
        f"Functions too long for a composition root:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_extracted_modules_exist():
    """Verify all extracted modules are present."""
    api_dir = _APP_CORE_PATH.parent
    expected = [
        "config.py",
        "paths.py",
        "job_repository.py",
        "session_store.py",
        "chat_lane_repository.py",
        "teacher_memory_core.py",
        "exam_utils.py",
        "core_utils.py",
        "profile_service.py",
        "assignment_data_service.py",
        "llm_routing_resolver.py",
        "llm_routing_proposals.py",
        "teacher_session_compaction_helpers.py",
        "teacher_memory_deps.py",
        "wiring/__init__.py",
        "wiring/chat_wiring.py",
        "wiring/assignment_wiring.py",
        "wiring/exam_wiring.py",
        "wiring/student_wiring.py",
        "wiring/teacher_wiring.py",
        "wiring/worker_wiring.py",
        "wiring/misc_wiring.py",
    ]
    missing = [m for m in expected if not (api_dir / m).exists()]
    assert not missing, f"Missing extracted modules: {missing}"


def test_wiring_modules_have_app_core_accessor():
    """Each wiring module must have access to _app_core() for multi-tenant support."""
    api_dir = _APP_CORE_PATH.parent
    wiring_files = list((api_dir / "wiring").glob("*_wiring.py"))
    assert len(wiring_files) >= 6, f"Expected >=6 wiring modules, found {len(wiring_files)}"
    for wf in wiring_files:
        source = wf.read_text(encoding="utf-8")
        has_local = "def _app_core()" in source
        has_import = "get_app_core" in source
        assert has_local or has_import, (
            f"{wf.name} missing _app_core() accessor (local or imported)"
        )
