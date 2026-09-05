import re
from pathlib import Path

# Honest floor(TOTAL) after leftover analysis/multimodal delete (2026-09-05 A4).
COVERAGE_FLOOR_N = 85


def test_ci_sets_backend_coverage_floor() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    match = re.search(r"--cov-fail-under=(\d+)", text)
    assert match is not None, "ci.yml must set --cov-fail-under"
    assert int(match.group(1)) == COVERAGE_FLOOR_N
    assert f"--cov-fail-under={COVERAGE_FLOOR_N}" in text


def test_ci_expands_backend_static_checks_to_additional_runtime_modules() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "services/api/config.py" in text
    assert "services/api/chat_job_state_machine.py" in text
    assert "services/api/fs_atomic.py" in text


def test_ci_runs_full_backend_suite_and_teacher_build() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'python -m pytest tests/ -x -q -m "not stress"' in text
    assert "npm run build:teacher" in text
    assert "Run maintainability guardrails" in text
    assert "Run assignment-only product guardrails" in text


def test_ci_does_not_run_analysis_rollout_as_product_gate() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run analysis rollout guardrails" not in text
    assert "scripts/analysis_strategy_eval.py" not in text
    assert "scripts/quality/check_analysis_policy.py" not in text
    assert "scripts/quality/check_analysis_preflight.py" not in text
    assert "analysis-rollout-artifacts" not in text
    assert "build_analysis_rollout_decision.py" not in text
