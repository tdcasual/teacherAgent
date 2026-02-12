from pathlib import Path


def test_ci_contains_quality_jobs() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "backend-quality" in text
    assert "frontend-quality" in text


def test_backend_smoke_tests_pin_pythonpath_and_pytest_entrypoint() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run backend smoke tests" in text
    assert "PYTHONPATH: ${{ github.workspace }}" in text
    assert "python -m pytest -q" in text


def test_ci_has_maintainability_guardrails_step() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run maintainability guardrails" in text
    assert "tests/test_tech_debt_targets.py" in text
    assert "tests/test_observability_store.py" in text
