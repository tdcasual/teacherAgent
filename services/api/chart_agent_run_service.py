from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class ChartAgentRunDeps:
    safe_int_arg: Callable[[Any, int, int, int], int]
    chart_bool: Callable[[Any, bool], bool]
    chart_engine: Callable[[Any], str]
    chart_packages: Callable[[Any], List[str]]
    chart_opencode_overrides: Callable[[Dict[str, Any]], Dict[str, Any]]
    resolve_opencode_status: Callable[[Any, Dict[str, Any]], Dict[str, Any]]
    app_root: Any
    uploads_dir: Any
    generate_candidate: Callable[[str, Any, str, str, int, int], Dict[str, Any]]
    generate_candidate_opencode: Callable[[str, Any, str, str, int, int, Dict[str, Any]], Dict[str, Any]]
    execute_chart_exec: Callable[[Dict[str, Any], Any, Any], Dict[str, Any]]
    default_code: Callable[[], str]


def chart_agent_run(args: Dict[str, Any], *, deps: ChartAgentRunDeps) -> Dict[str, Any]:
    task = str(args.get("task") or "").strip()
    if not task:
        return {"error": "task_required"}

    timeout_sec = deps.safe_int_arg(args.get("timeout_sec"), default=180, minimum=30, maximum=3600)
    max_retries = deps.safe_int_arg(args.get("max_retries"), default=3, minimum=1, maximum=6)
    auto_install = deps.chart_bool(args.get("auto_install"), default=True)
    explicit_engine = bool(str(args.get("engine") or "").strip())
    requested_engine = deps.chart_engine(args.get("engine"))
    chart_hint = str(args.get("chart_hint") or task[:120]).strip()
    save_as = str(args.get("save_as") or "main.png").strip() or "main.png"
    input_data = args.get("input_data")
    requested_packages = deps.chart_packages(args.get("packages"))
    opencode_overrides = deps.chart_opencode_overrides(args)
    opencode_status = deps.resolve_opencode_status(deps.app_root, overrides=opencode_overrides)
    opencode_cfg = opencode_status.get("config") if isinstance(opencode_status.get("config"), dict) else {}

    effective_engine = requested_engine
    if requested_engine == "opencode" and not opencode_status.get("available") and not explicit_engine:
        effective_engine = "llm"

    effective_max_retries = max_retries
    if effective_engine == "opencode" and isinstance(opencode_cfg, dict):
        effective_max_retries = deps.safe_int_arg(opencode_cfg.get("max_retries"), default=max_retries, minimum=1, maximum=6)
    elif effective_engine == "auto" and opencode_status.get("available") and isinstance(opencode_cfg, dict):
        effective_max_retries = deps.safe_int_arg(opencode_cfg.get("max_retries"), default=max_retries, minimum=1, maximum=6)

    if requested_engine == "opencode" and explicit_engine:
        if not opencode_status.get("enabled"):
            return {
                "ok": False,
                "error": "opencode_disabled",
                "detail": "opencode bridge disabled",
                "engine_requested": requested_engine,
                "opencode_status": opencode_status,
            }
        if not opencode_status.get("available"):
            return {
                "ok": False,
                "error": "opencode_unavailable",
                "detail": opencode_status.get("reason") or "opencode unavailable",
                "engine_requested": requested_engine,
                "opencode_status": opencode_status,
            }

    attempts: List[Dict[str, Any]] = []
    last_error = ""
    previous_code = ""

    for attempt in range(1, effective_max_retries + 1):
        attempt_engine = effective_engine
        if effective_engine == "auto":
            attempt_engine = "opencode" if opencode_status.get("available") else "llm"

        if attempt_engine == "opencode":
            candidate = deps.generate_candidate_opencode(
                task=task,
                input_data=input_data,
                last_error=last_error,
                previous_code=previous_code,
                attempt=attempt,
                max_retries=effective_max_retries,
                opencode_overrides=opencode_overrides,
            )
            if effective_engine == "auto" and not str(candidate.get("python_code") or "").strip():
                fallback_candidate = deps.generate_candidate(
                    task=task,
                    input_data=input_data,
                    last_error=last_error,
                    previous_code=previous_code,
                    attempt=attempt,
                    max_retries=effective_max_retries,
                )
                fallback_candidate["fallback_from"] = "opencode"
                candidate = fallback_candidate
                attempt_engine = "llm"
        else:
            candidate = deps.generate_candidate(
                task=task,
                input_data=input_data,
                last_error=last_error,
                previous_code=previous_code,
                attempt=attempt,
                max_retries=effective_max_retries,
            )

        python_code = str(candidate.get("python_code") or "").strip() or deps.default_code()
        llm_packages = deps.chart_packages(candidate.get("packages"))
        merged_packages: List[str] = []
        seen: set[str] = set()
        for pkg in requested_packages + llm_packages:
            key = pkg.lower()
            if key in seen:
                continue
            seen.add(key)
            merged_packages.append(pkg)

        exec_res = deps.execute_chart_exec(
            {
                "python_code": python_code,
                "input_data": input_data,
                "chart_hint": chart_hint,
                "timeout_sec": timeout_sec,
                "save_as": save_as,
                "auto_install": auto_install,
                "packages": merged_packages,
                "max_retries": 2,
            },
            app_root=deps.app_root,
            uploads_dir=deps.uploads_dir,
        )

        attempts.append(
            {
                "attempt": attempt,
                "engine": attempt_engine,
                "packages": merged_packages,
                "summary": candidate.get("summary") or "",
                "code_preview": python_code[:1200],
                "codegen_error": candidate.get("error"),
                "codegen_meta": candidate.get("meta") if isinstance(candidate.get("meta"), dict) else None,
                "execution": {
                    "ok": bool(exec_res.get("ok")),
                    "run_id": exec_res.get("run_id"),
                    "exit_code": exec_res.get("exit_code"),
                    "timed_out": exec_res.get("timed_out"),
                    "image_url": exec_res.get("image_url"),
                    "meta_url": exec_res.get("meta_url"),
                    "stderr": str(exec_res.get("stderr") or "")[:500],
                },
            }
        )

        if exec_res.get("ok") and exec_res.get("image_url"):
            title = str(args.get("title") or "图表结果").strip() or "图表结果"
            markdown = f"### {title}\n\n![{title}]({exec_res.get('image_url')})"
            return {
                "ok": True,
                "task": task,
                "attempt_used": attempt,
                "engine_requested": requested_engine,
                "engine_used": attempt_engine,
                "image_url": exec_res.get("image_url"),
                "meta_url": exec_res.get("meta_url"),
                "run_id": exec_res.get("run_id"),
                "artifacts": exec_res.get("artifacts") or [],
                "installed_packages": exec_res.get("installed_packages") or [],
                "python_executable": exec_res.get("python_executable"),
                "markdown": markdown,
                "attempts": attempts,
                "opencode_status": opencode_status if requested_engine in {"auto", "opencode"} else None,
            }

        previous_code = python_code
        last_error = str(exec_res.get("stderr") or exec_res.get("error") or "unknown_error")

    return {
        "ok": False,
        "error": "chart_agent_failed",
        "task": task,
        "max_retries": effective_max_retries,
        "engine_requested": requested_engine,
        "last_error": last_error[:1200],
        "attempts": attempts,
        "opencode_status": opencode_status if requested_engine in {"auto", "opencode"} else None,
    }
