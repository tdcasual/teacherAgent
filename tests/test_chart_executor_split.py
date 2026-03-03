from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import services.api.chart_executor as chart_executor


def test_chart_executor_imports_policy_and_runner_services() -> None:
    source = Path("services/api/chart_executor.py").read_text(encoding="utf-8")
    assert "from .chart.policy_service import prepare_chart_exec_policy" in source
    assert "from .chart.runner_service import execute_with_global_semaphore" in source


def test_execute_chart_exec_delegates_to_runner_service(monkeypatch: Any, tmp_path: Path) -> None:
    captured: Dict[str, Any] = {}

    def _fake_prepare_chart_exec_policy(
        exec_args: Dict[str, Any], python_code: str, **_: Any
    ) -> Dict[str, Any]:
        captured["prepared"] = {
            "exec_args": dict(exec_args),
            "python_code": python_code,
        }
        return {
            "execution_profile": "sandboxed",
            "audit_context": {"source": "unknown", "role": "", "actor": ""},
            "trusted_alerts": [],
            "error_result": None,
            "scan_result": None,
        }

    def _fake_execute_with_global_semaphore(
        *,
        exec_args: Dict[str, Any],
        app_root: Path,
        uploads_dir: Path,
        python_code: str,
        execution_profile: str,
        audit_context: Dict[str, str],
        trusted_alerts: list[str],
        execute_inner: Any,
        audit_log: Any,
        semaphore: Any,
    ) -> Dict[str, Any]:
        captured["runner"] = {
            "exec_args": dict(exec_args),
            "app_root": app_root,
            "uploads_dir": uploads_dir,
            "python_code": python_code,
            "execution_profile": execution_profile,
            "audit_context": dict(audit_context),
            "trusted_alerts": list(trusted_alerts),
            "execute_inner": execute_inner,
            "audit_log": audit_log,
            "semaphore": semaphore,
        }
        return {"ok": True, "execution_profile": execution_profile}

    monkeypatch.setattr(
        chart_executor,
        "prepare_chart_exec_policy",
        _fake_prepare_chart_exec_policy,
        raising=False,
    )
    monkeypatch.setattr(
        chart_executor,
        "execute_with_global_semaphore",
        _fake_execute_with_global_semaphore,
        raising=False,
    )

    result = chart_executor.execute_chart_exec(
        {"python_code": "print('hello')"},
        app_root=tmp_path,
        uploads_dir=tmp_path,
    )

    assert result == {"ok": True, "execution_profile": "sandboxed"}
    assert captured["prepared"]["python_code"] == "print('hello')"
    assert captured["runner"]["execution_profile"] == "sandboxed"
    assert captured["runner"]["app_root"] == tmp_path
    assert captured["runner"]["uploads_dir"] == tmp_path
