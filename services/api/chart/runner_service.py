from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List


def execute_with_global_semaphore(
    *,
    exec_args: Dict[str, Any],
    app_root: Path,
    uploads_dir: Path,
    python_code: str,
    execution_profile: str,
    audit_context: Dict[str, str],
    trusted_alerts: List[str],
    execute_inner: Callable[[Dict[str, Any], Path, Path, str, str], Dict[str, Any]],
    audit_log: Callable[[str, Dict[str, Any]], None],
    semaphore: Any,
    acquire_timeout_sec: float = 30.0,
) -> Dict[str, Any]:
    acquired = semaphore.acquire(timeout=acquire_timeout_sec)
    if not acquired:
        return {"error": "chart_exec_busy", "message": "Too many concurrent chart executions"}

    try:
        result = execute_inner(
            exec_args,
            app_root,
            uploads_dir,
            python_code,
            execution_profile,
        )
        audit_log(
            "chart.exec.finish",
            {
                "execution_profile": execution_profile,
                "source": audit_context.get("source"),
                "role": audit_context.get("role"),
                "actor": audit_context.get("actor"),
                "ok": bool(result.get("ok")),
                "run_id": result.get("run_id"),
                "exit_code": result.get("exit_code"),
                "timed_out": bool(result.get("timed_out")),
                "auto_install": bool(result.get("auto_install")),
                "requested_packages": result.get("requested_packages") or [],
                "installed_packages": result.get("installed_packages") or [],
                "trusted_risk_alerts": trusted_alerts,
            },
        )
        return result
    finally:
        semaphore.release()

