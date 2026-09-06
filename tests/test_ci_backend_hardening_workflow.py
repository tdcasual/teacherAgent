from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Honest floor(TOTAL) after leftover analysis/multimodal delete (2026-09-05 A4).
COVERAGE_FLOOR_N = 85

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_MYPY_GATE_PATH = _REPO_ROOT / "config" / "mypy_gate_files.txt"
_BUDGET_PATH = _REPO_ROOT / "config" / "backend_quality_budget.json"

# Previous CI mypy whitelist. The gate list may only grow from this set.
_PREVIOUS_CI_MYPY_WHITELIST = (
    "services/api/settings.py",
    "services/api/config.py",
    "services/api/paths.py",
    "services/api/auth_service.py",
    "services/api/rate_limit.py",
    "services/api/chat_job_state_machine.py",
    "services/api/chat_status_service.py",
    "services/api/chat_idempotency_service.py",
    "services/api/chat_redis_lane_store.py",
    "services/api/chat_lock_service.py",
    "services/api/chat_lane_repository.py",
    "services/api/job_repository.py",
    "services/api/session_store.py",
    "services/api/profile_service.py",
    "services/api/global_limits.py",
    "services/api/observability.py",
    "services/api/request_context.py",
    "services/api/fs_atomic.py",
    "services/api/runtime/runtime_manager.py",
    "services/api/teacher_model_config_service.py",
    "services/api/teacher_provider_registry_service.py",
    "services/api/chart_executor.py",
    "services/api/chart_sandbox.py",
    "services/api/core_utils.py",
)


def _load_mypy_gate_files() -> list[str]:
    files: list[str] = []
    for raw in _MYPY_GATE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        files.append(line)
    return files


def _ci_mypy_step(text: str) -> str:
    marker = "python -m mypy"
    start = text.find(marker)
    assert start != -1, "ci.yml must run python -m mypy"
    name_start = text.rfind("- name:", 0, start)
    assert name_start != -1
    end = text.find("\n      - name:", start)
    return text[name_start:] if end == -1 else text[name_start:end]


def test_ci_sets_backend_coverage_floor() -> None:
    text = _CI_YML.read_text(encoding="utf-8")
    match = re.search(r"--cov-fail-under=(\d+)", text)
    assert match is not None, "ci.yml must set --cov-fail-under"
    assert int(match.group(1)) == COVERAGE_FLOOR_N
    assert f"--cov-fail-under={COVERAGE_FLOOR_N}" in text


def test_ci_mypy_gate_reads_allowlist_file() -> None:
    text = _CI_YML.read_text(encoding="utf-8")
    step = _ci_mypy_step(text)
    assert "config/mypy_gate_files.txt" in step
    assert "--ignore-missing-imports" in step
    assert "--follow-imports=skip" in step
    assert "--strict" not in step
    assert "services/api/config.py" not in step
    assert "services/api/chat_job_state_machine.py" not in step
    assert "services/api/fs_atomic.py" not in step


def test_mypy_gate_files_grow_from_previous_ci_whitelist() -> None:
    gated = _load_mypy_gate_files()
    gated_set = set(gated)
    missing = [path for path in _PREVIOUS_CI_MYPY_WHITELIST if path not in gated_set]
    assert missing == [], f"mypy gate dropped previous files: {missing}"
    assert "services/api/assignment/visibility.py" in gated_set
    assert "services/api/subject_pack_service.py" in gated_set
    for path in gated:
        assert (_REPO_ROOT / path).is_file(), path


def test_mypy_gate_files_are_skip_imports_clean() -> None:
    files = _load_mypy_gate_files()
    assert files, "config/mypy_gate_files.txt must list at least one module"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--ignore-missing-imports",
            "--follow-imports=skip",
            *files,
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    assert proc.returncode == 0, output


def test_mypy_max_budget_remains_observation_only() -> None:
    data = json.loads(_BUDGET_PATH.read_text(encoding="utf-8"))
    assert data["mypy_max"] == 19


def test_ci_runs_full_backend_suite_and_teacher_build() -> None:
    text = _CI_YML.read_text(encoding="utf-8")
    assert 'python -m pytest tests/ -x -q -m "not stress"' in text
    assert "npm run build:teacher" in text
    assert "Run maintainability guardrails" in text
    assert "Run assignment-only product guardrails" in text


def test_ci_does_not_run_analysis_rollout_as_product_gate() -> None:
    text = _CI_YML.read_text(encoding="utf-8")
    assert "Run analysis rollout guardrails" not in text
    assert "scripts/analysis_strategy_eval.py" not in text
    assert "scripts/quality/check_analysis_policy.py" not in text
    assert "scripts/quality/check_analysis_preflight.py" not in text
    assert "analysis-rollout-artifacts" not in text
    assert "build_analysis_rollout_decision.py" not in text
