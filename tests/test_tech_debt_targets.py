"""Debt-governance targets that must remain enforced by CI."""

from pathlib import Path

_STUDENT_APP_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "student"
    / "src"
    / "App.tsx"
)


def test_student_app_line_budget() -> None:
    lines = _STUDENT_APP_PATH.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    assert line_count < 1200, (
        f"student App.tsx is {line_count} lines (limit 1200). "
        "Continue extracting send flow/session sidebar state hooks."
    )


def test_ci_runs_maintainability_guardrails() -> None:
    ci_text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run maintainability guardrails" in ci_text
    assert "tests/test_tech_debt_targets.py" in ci_text
    assert "tests/test_app_core_import_fanout.py" in ci_text
