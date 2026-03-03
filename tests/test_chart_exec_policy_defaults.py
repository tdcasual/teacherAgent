from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import services.api.chart_executor as chart_executor
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
