from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chart import runner_service as _chart_runner_service
from .chart.env_service import (
    _acquire_chart_env_lease,
    _chart_env_gc_policy,
    _chart_envs_root,
    _cleanup_stale_chart_env_leases,
    _delete_chart_env_dir,
    _dir_size_bytes,
    _ensure_venv,
    _env_gc_state_path,
    _env_int,
    _env_last_used_ts,
    _env_lease_path,
    _env_python_path,
    _env_root,
    _has_active_chart_env_lease,
    _mark_chart_env_used,
    _maybe_prune_chart_envs,
    _numeric_ts,
    _pip_install,
    _prune_chart_envs,
    _read_json_dict,
    _release_chart_env_lease,
    _venv_scope,
    _write_json_dict,
)
from .chart.normalize import (
    _clip_text,
    _extract_missing_module,
    _format_artifacts_markdown,
    _iso_now,
    _normalize_bool,
    _normalize_packages,
    _normalize_retries,
    _normalize_timeout,
    _safe_any_file_name,
    _safe_file_name,
    _safe_run_id,
)
from .chart.policy_service import prepare_chart_exec_policy
from .chart.runner_service import execute_with_global_semaphore

_build_runner_source = _chart_runner_service._build_runner_source
_execute_chart_exec_inner = _chart_runner_service._execute_chart_exec_inner

_log = logging.getLogger(__name__)

_TRUSTED_FORBIDDEN_SOURCES = frozenset({"tool_loop", "chat", "llm"})
_TRUSTED_ALERT_PATTERNS = [
    (re.compile(r"\bsubprocess\b"), "subprocess"),
    (re.compile(r"\bos\.system\s*\("), "os.system"),
    (re.compile(r"\bos\.popen\s*\("), "os.popen"),
    (re.compile(r"\beval\s*\("), "eval"),
    (re.compile(r"\bexec\s*\("), "exec"),
    (re.compile(r"\b__import__\s*\("), "__import__"),
    (re.compile(r"\bsocket\b"), "socket"),
]

# Re-export stdlib handles so existing tests can monkeypatch ce.subprocess/os/etc.
__all__ = [
    "execute_chart_exec",
    "os",
    "resolve_chart_image_path",
    "resolve_chart_run_meta_path",
    "shutil",
    "subprocess",
    "time",
    "uuid",
    "_acquire_chart_env_lease",
    "_build_runner_source",
    "_chart_env_gc_policy",
    "_chart_envs_root",
    "_cleanup_stale_chart_env_leases",
    "_clip_text",
    "_delete_chart_env_dir",
    "_dir_size_bytes",
    "_ensure_venv",
    "_env_gc_state_path",
    "_env_int",
    "_env_last_used_ts",
    "_env_lease_path",
    "_env_python_path",
    "_env_root",
    "_execute_chart_exec_inner",
    "_extract_missing_module",
    "_format_artifacts_markdown",
    "_has_active_chart_env_lease",
    "_iso_now",
    "_mark_chart_env_used",
    "_maybe_prune_chart_envs",
    "_normalize_bool",
    "_normalize_packages",
    "_normalize_retries",
    "_normalize_timeout",
    "_numeric_ts",
    "_pip_install",
    "_prune_chart_envs",
    "_read_json_dict",
    "_release_chart_env_lease",
    "_safe_any_file_name",
    "_safe_file_name",
    "_safe_run_id",
    "_venv_scope",
    "_write_json_dict",
]


def _parse_csv_lower_set(value: Any) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    out: set[str] = set()
    for item in re.split(r"[,\s;；，]+", text):
        token = str(item or "").strip().lower()
        if token:
            out.add(token)
    return out


def _chart_exec_audit_context(args: Dict[str, Any]) -> Dict[str, str]:
    source = str(args.get("_audit_source") or args.get("source") or "").strip().lower() or "unknown"
    role = str(args.get("_audit_role") or "").strip().lower()
    actor = str(args.get("_audit_actor") or "").strip()
    return {"source": source, "role": role, "actor": actor}


def _trusted_risk_alerts(
    python_code: str,
    *,
    auto_install: bool,
    requested_packages: List[str],
) -> List[str]:
    alerts: List[str] = []
    for pattern, label in _TRUSTED_ALERT_PATTERNS:
        if pattern.search(python_code or ""):
            alerts.append(label)
    if auto_install and requested_packages:
        alerts.append("auto_install_with_packages")
    return alerts


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _trusted_policy_denial(*, role: str, source: str) -> Optional[str]:
    # Empty allowlist is deny. Previously empty meant allow.
    if not _env_truthy("CHART_EXEC_TRUSTED_ENABLED"):
        return "trusted_not_enabled"
    allowed_sources = _parse_csv_lower_set(os.getenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES"))
    allowed_roles = _parse_csv_lower_set(os.getenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES"))
    if not allowed_sources or not allowed_roles:
        return "trusted_allowlist_empty"
    src = str(source or "").strip().lower()
    role_norm = str(role or "").strip().lower()
    if src not in allowed_sources or src in _TRUSTED_FORBIDDEN_SOURCES:
        return "trusted_source_not_allowed"
    if role_norm not in allowed_roles:
        return "trusted_role_not_allowed"
    return None


def _audit_log(event: str, payload: Dict[str, Any]) -> None:
    record = {"ts": _iso_now(), "event": event}
    record.update(payload)
    try:
        _log.info("chart_exec.audit %s", json.dumps(record, ensure_ascii=False, default=str))
    except Exception:  # policy: allowed-broad-except
        _log.debug("chart exec audit log failed for event=%s", event, exc_info=True)


def execute_chart_exec(args: Dict[str, Any], app_root: Path, uploads_dir: Path) -> Dict[str, Any]:
    from .chart_sandbox import (
        scan_code_patterns,
    )
    from .global_limits import GLOBAL_CHART_EXEC_SEMAPHORE

    exec_args = dict(args or {})
    python_code = str(exec_args.get("python_code") or "")
    if not python_code.strip():
        return {"error": "missing_python_code"}

    policy = prepare_chart_exec_policy(
        exec_args,
        python_code,
        chart_exec_audit_context=_chart_exec_audit_context,
        normalize_bool=_normalize_bool,
        normalize_packages=_normalize_packages,
        trusted_risk_alerts_fn=_trusted_risk_alerts,
        trusted_policy_denial_fn=_trusted_policy_denial,
        audit_log=_audit_log,
        scan_code_patterns=scan_code_patterns,
        logger=_log,
    )
    error_result = policy.get("error_result")
    if isinstance(error_result, dict):
        return error_result

    scan_result = policy.get("scan_result")
    if isinstance(scan_result, dict):
        return scan_result

    execution_profile = str(policy.get("execution_profile") or "sandboxed")
    audit_context = policy.get("audit_context")
    trusted_alerts = policy.get("trusted_alerts")
    return execute_with_global_semaphore(
        exec_args=exec_args,
        app_root=app_root,
        uploads_dir=uploads_dir,
        python_code=python_code,
        execution_profile=execution_profile,
        audit_context=audit_context if isinstance(audit_context, dict) else {},
        trusted_alerts=trusted_alerts if isinstance(trusted_alerts, list) else [],
        execute_inner=_execute_chart_exec_inner,
        audit_log=_audit_log,
        semaphore=GLOBAL_CHART_EXEC_SEMAPHORE,
    )


def resolve_chart_image_path(uploads_dir: Path, run_id: str, file_name: str) -> Optional[Path]:
    safe_run_id = _safe_run_id(run_id)
    safe_name = _safe_any_file_name(file_name)
    if not safe_run_id or not safe_name:
        return None
    root = (uploads_dir / "charts").resolve()
    path = (root / safe_run_id / safe_name).resolve()
    if root not in path.parents:
        return None
    if not path.exists() or not path.is_file():
        return None
    return path


def resolve_chart_run_meta_path(uploads_dir: Path, run_id: str) -> Optional[Path]:
    safe_run_id = _safe_run_id(run_id)
    if not safe_run_id:
        return None
    root = (uploads_dir / "chart_runs").resolve()
    path = (root / safe_run_id / "meta.json").resolve()
    if root not in path.parents:
        return None
    if not path.exists() or not path.is_file():
        return None
    return path
