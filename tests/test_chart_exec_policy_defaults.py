from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import services.api.chart_executor as chart_executor
import services.api.chart_sandbox as chart_sandbox
import services.api.global_limits as global_limits


class _AlwaysAcquireSemaphore:
    def acquire(self, timeout: float = 0.0) -> bool:
        return True

    def release(self) -> None:
        return None


def _patch_fast_exec(monkeypatch: Any, observed: Dict[str, str]) -> None:
    def _fake_execute_inner(
        args: Dict[str, Any],
        app_root: Path,
        uploads_dir: Path,
        python_code: str,
        execution_profile: str,
    ) -> Dict[str, Any]:
        observed["execution_profile"] = execution_profile
        return {"ok": True, "execution_profile": execution_profile}

    monkeypatch.setattr(global_limits, "GLOBAL_CHART_EXEC_SEMAPHORE", _AlwaysAcquireSemaphore())
    monkeypatch.setattr(chart_executor, "_execute_chart_exec_inner", _fake_execute_inner)


def test_execute_chart_exec_defaults_to_sandboxed_profile(monkeypatch: Any, tmp_path: Path) -> None:
    observed: Dict[str, str] = {}
    _patch_fast_exec(monkeypatch, observed)

    result = chart_executor.execute_chart_exec(
        {"python_code": "print('hello')"},
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )

    assert result.get("execution_profile") == "sandboxed"
    assert observed.get("execution_profile") == "sandboxed"


def test_execute_chart_exec_invalid_profile_falls_back_to_sandboxed(monkeypatch: Any, tmp_path: Path) -> None:
    observed: Dict[str, str] = {}
    _patch_fast_exec(monkeypatch, observed)

    result = chart_executor.execute_chart_exec(
        {"python_code": "print('hello')", "execution_profile": "unknown_profile"},
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )

    assert result.get("execution_profile") == "sandboxed"
    assert observed.get("execution_profile") == "sandboxed"


def test_execute_chart_exec_keeps_template_profile_for_exam_source(monkeypatch: Any, tmp_path: Path) -> None:
    observed: Dict[str, str] = {}
    _patch_fast_exec(monkeypatch, observed)

    result = chart_executor.execute_chart_exec(
        {
            "python_code": "print('hello')",
            "execution_profile": "template",
            "_audit_source": "exam.analysis.charts.generate",
            "_audit_role": "teacher",
        },
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )

    assert result.get("execution_profile") == "template"
    assert observed.get("execution_profile") == "template"


def test_execute_chart_exec_ignores_trusted_from_llm_sources(monkeypatch: Any, tmp_path: Path) -> None:
    observed: Dict[str, str] = {}
    _patch_fast_exec(monkeypatch, observed)
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ENABLED", "1")
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", "tool_dispatch.chart.exec,tool_loop")
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", "teacher")

    result = chart_executor.execute_chart_exec(
        {
            "python_code": "print('hello')",
            "execution_profile": "trusted",
            "_audit_source": "tool_dispatch.chart.exec",
            "_audit_role": "teacher",
        },
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )

    assert result.get("execution_profile") == "sandboxed"
    assert observed.get("execution_profile") == "sandboxed"


def test_execute_chart_exec_denies_trusted_when_not_enabled(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.delenv("CHART_EXEC_TRUSTED_ENABLED", raising=False)
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", "operator_cli")
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", "admin")

    result = chart_executor.execute_chart_exec(
        {
            "python_code": "print('hello')",
            "execution_profile": "trusted",
            "_audit_source": "operator_cli",
            "_audit_role": "admin",
        },
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )

    assert result.get("error") == "chart_exec_trusted_forbidden"
    assert result.get("detail") == "trusted_not_enabled"


def test_execute_chart_exec_scans_sandboxed_template_and_trusted(monkeypatch: Any, tmp_path: Path) -> None:
    observed: Dict[str, str] = {}
    _patch_fast_exec(monkeypatch, observed)
    scanned: List[Tuple[str, str]] = []

    def _scan(code: str, profile: str) -> Optional[Dict[str, Any]]:
        scanned.append((code, profile))
        return None

    monkeypatch.setattr(chart_sandbox, "scan_code_patterns", _scan)
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ENABLED", "1")
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", "operator_cli")
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", "admin")

    chart_executor.execute_chart_exec(
        {"python_code": "print('sb')", "execution_profile": "sandboxed"},
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )
    chart_executor.execute_chart_exec(
        {
            "python_code": "print('tp')",
            "execution_profile": "template",
            "_audit_source": "exam.analysis.charts.generate",
        },
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )
    chart_executor.execute_chart_exec(
        {
            "python_code": "print('tr')",
            "execution_profile": "trusted",
            "_audit_source": "operator_cli",
            "_audit_role": "admin",
        },
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )

    profiles = [item[1] for item in scanned]
    assert profiles == ["sandboxed", "template", "trusted"]

