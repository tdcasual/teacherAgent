"""Debt-governance targets that must remain enforced by CI."""

from pathlib import Path

_STUDENT_APP_PATH = (
    Path(__file__).resolve().parent.parent / "frontend" / "apps" / "student" / "src" / "App.tsx"
)

STRUCTURE_TEST_GLOBS = (
    "tests/test_*structure*.py",
    "tests/test_*split*.py",
    "tests/test_*budget*.py",
    "tests/test_*leftover*.py",
    "tests/test_no_*.py",
    "tests/test_*guard*.py",
)
STRUCTURE_TEST_COUNT_FROZEN = 84


def test_structure_test_count_frozen() -> None:
    tests_dir = Path("tests")
    names = set()
    for pattern in STRUCTURE_TEST_GLOBS:
        glob = pattern[len("tests/") :] if pattern.startswith("tests/") else pattern
        names.update(path.name for path in tests_dir.glob(glob))
    assert len(names) == STRUCTURE_TEST_COUNT_FROZEN, (
        f"structure-test count is {len(names)}, frozen at {STRUCTURE_TEST_COUNT_FROZEN}"
    )


def test_student_app_line_budget() -> None:
    lines = _STUDENT_APP_PATH.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    assert line_count < 920, (
        f"student App.tsx is {line_count} lines (limit 920). "
        "Continue extracting send flow/session sidebar state hooks."
    )


def test_ci_runs_maintainability_guardrails() -> None:
    ci_text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run maintainability guardrails" in ci_text
    assert "tests/test_tech_debt_targets.py" in ci_text
    assert "tests/test_app_core_import_fanout.py" in ci_text
    assert "tests/test_chat_workers_signature_fallback_guard.py" in ci_text
