from pathlib import Path


def test_ci_has_smoke_e2e_gate() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "smoke-e2e" in text
    assert "Run smoke E2E" in text
    assert "npm run e2e:smoke" in text


def test_ci_has_parallel_playwright_isolation_step() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run parallel Playwright isolation check" in text
    assert "npm run e2e:teacher -- e2e/teacher-session-sidebar.spec.ts" in text
    assert "npm run e2e:student -- e2e/student-session-sidebar.spec.ts" in text
    assert "wait $teacher_pid" in text
    assert "wait $student_pid" in text
