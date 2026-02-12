from pathlib import Path


def test_ci_sets_backend_coverage_floor() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "--cov-fail-under=84" in text


def test_ci_expands_backend_static_checks_to_additional_runtime_modules() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "services/api/config.py" in text
    assert "services/api/chat_job_state_machine.py" in text
    assert "services/api/fs_atomic.py" in text
