from pathlib import Path


def test_ci_sets_backend_coverage_floor() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert '--cov-fail-under=84' in text


def test_ci_expands_backend_static_checks_to_additional_runtime_modules() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'services/api/config.py' in text
    assert 'services/api/chat_job_state_machine.py' in text
    assert 'services/api/fs_atomic.py' in text


def test_ci_runs_full_backend_suite_and_teacher_build_for_survey_rollout() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'python -m pytest tests/ -x -q -m "not stress"' in text
    assert 'npm run build:teacher' in text
    assert 'Run maintainability guardrails' in text


def test_ci_runs_analysis_eval_and_docs_guardrails_for_multi_domain_rollout() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'scripts/analysis_strategy_eval.py --fixtures tests/fixtures --json --summary-only' in text
    assert 'tests/test_analysis_strategy_eval.py' in text
    assert 'tests/test_docs_architecture_presence.py' in text
    assert 'tests/test_ci_backend_hardening_workflow.py' in text


def test_ci_runs_analysis_domain_contract_checker() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'scripts/check_analysis_domain_contract.py --json' in text


def test_ci_runs_analysis_policy_gate() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'scripts/quality/check_analysis_policy.py' in text


def test_ci_runs_unified_analysis_preflight_gate() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'scripts/quality/check_analysis_preflight.py' in text
    assert 'tests/fixtures/analysis_preflight/review_feedback.jsonl' in text
    assert 'tests/fixtures/analysis_preflight/metrics.json' in text
    assert 'tests/fixtures/analysis_preflight/baseline' in text
    assert 'tests/fixtures/analysis_preflight/candidate' in text


def test_ci_uploads_analysis_rollout_artifacts() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'analysis-artifacts' in text
    assert 'actions/upload-artifact' in text


def test_ci_writes_analysis_rollout_summary() -> None:
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'GITHUB_STEP_SUMMARY' in text
    assert 'analysis-policy.json' in text
    assert 'analysis-preflight.json' in text
