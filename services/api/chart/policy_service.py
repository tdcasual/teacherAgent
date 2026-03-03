from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional


def prepare_chart_exec_policy(
    exec_args: Dict[str, Any],
    python_code: str,
    *,
    chart_exec_audit_context: Callable[[Dict[str, Any]], Dict[str, str]],
    normalize_bool: Callable[[Any, bool], bool],
    normalize_packages: Callable[[Any], List[str]],
    trusted_risk_alerts_fn: Callable[..., List[str]],
    trusted_policy_denial_fn: Callable[..., Optional[str]],
    audit_log: Callable[[str, Dict[str, Any]], None],
    scan_code_patterns: Callable[[str, str], Optional[Dict[str, Any]]],
    logger: logging.Logger,
) -> Dict[str, Any]:
    execution_profile = str(exec_args.get("execution_profile") or "sandboxed").strip()
    if execution_profile not in ("template", "trusted", "sandboxed"):
        execution_profile = "sandboxed"

    audit_context = chart_exec_audit_context(exec_args)
    auto_install = normalize_bool(exec_args.get("auto_install"), False)
    requested_packages = normalize_packages(exec_args.get("packages"))
    trusted_alerts: List[str] = []

    if execution_profile == "trusted":
        trusted_alerts = trusted_risk_alerts_fn(
            python_code,
            auto_install=auto_install,
            requested_packages=requested_packages,
        )
        if trusted_alerts:
            logger.warning("chart.exec trusted profile risk alerts: %s", ",".join(trusted_alerts))
        denied_reason = trusted_policy_denial_fn(
            role=audit_context.get("role") or "",
            source=audit_context.get("source") or "",
        )
        if denied_reason:
            audit_log(
                "chart.exec.policy.denied",
                {
                    "execution_profile": execution_profile,
                    "source": audit_context.get("source"),
                    "role": audit_context.get("role"),
                    "actor": audit_context.get("actor"),
                    "detail": denied_reason,
                },
            )
            return {
                "execution_profile": execution_profile,
                "audit_context": audit_context,
                "trusted_alerts": trusted_alerts,
                "scan_result": None,
                "error_result": {
                    "error": "chart_exec_trusted_forbidden",
                    "detail": denied_reason,
                    "execution_profile": execution_profile,
                },
            }

    exec_args["_audit_context"] = audit_context
    exec_args["_trusted_risk_alerts"] = list(trusted_alerts)
    audit_log(
        "chart.exec.start",
        {
            "execution_profile": execution_profile,
            "source": audit_context.get("source"),
            "role": audit_context.get("role"),
            "actor": audit_context.get("actor"),
            "auto_install": auto_install,
            "requested_packages": requested_packages,
            "trusted_risk_alerts": trusted_alerts,
        },
    )

    scan_result = None
    if execution_profile == "sandboxed":
        scan_result = scan_code_patterns(python_code, execution_profile)

    return {
        "execution_profile": execution_profile,
        "audit_context": audit_context,
        "trusted_alerts": trusted_alerts,
        "scan_result": scan_result,
        "error_result": None,
    }
