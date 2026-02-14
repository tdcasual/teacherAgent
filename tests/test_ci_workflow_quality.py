from pathlib import Path


def test_ci_contains_quality_jobs() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "backend-quality" in text
    assert "frontend-quality" in text


def test_backend_smoke_tests_pin_pythonpath_and_pytest_entrypoint() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run full backend test suite" in text
    assert "PYTHONPATH: ${{ github.workspace }}" in text
    assert "python -m pytest" in text


def test_ci_has_maintainability_guardrails_step() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run maintainability guardrails" in text
    assert "tests/test_tech_debt_targets.py" in text
    assert "tests/test_observability_store.py" in text


def test_ci_has_backend_quality_budget_check_step() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Check backend quality budget" in text
    assert "python scripts/quality/check_backend_quality_budget.py" in text


def test_frontend_ci_has_types_install_integrity_step() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Verify frontend @types install integrity" in text
    assert "npm run check:types-install" in text


def test_frontend_jobs_emit_dependency_install_metrics_summary() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "id: setup-node-frontend-quality" in text
    assert "id: install-frontend-deps-quality" in text
    assert "steps.setup-node-frontend-quality.outputs.cache-hit" in text
    assert "steps.install-frontend-deps-quality.outputs.duration_seconds" in text

    assert "id: setup-node-smoke-e2e" in text
    assert "id: install-frontend-deps-smoke-e2e" in text
    assert "steps.setup-node-smoke-e2e.outputs.cache-hit" in text
    assert "steps.install-frontend-deps-smoke-e2e.outputs.duration_seconds" in text

    assert "id: setup-node-student-critical-e2e" in text
    assert "id: install-frontend-deps-student-critical-e2e" in text
    assert "steps.setup-node-student-critical-e2e.outputs.cache-hit" in text
    assert "steps.install-frontend-deps-student-critical-e2e.outputs.duration_seconds" in text

    assert "Frontend dependency install metrics" in text
    assert "GITHUB_STEP_SUMMARY" in text
