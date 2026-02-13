from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

_log = logging.getLogger(__name__)

_CJK_CHAR_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
_GLYPH_MISSING_RE = re.compile(r"Glyph\s+(\d+)\b.*missing from font\(s\)", re.I)
_BENIGN_WARNING_PATTERNS = (
    "matplotlib created a temporary cache directory",
    "could not save font_manager cache sandbox",
    "mkdir -p failed for path /home/appuser/.config/matplotlib",
)


def _contains_cjk_text(text: str) -> bool:
    return bool(_CJK_CHAR_RE.search(str(text or "")))


def _is_cjk_codepoint(codepoint: int) -> bool:
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2CEAF
    )


def _has_missing_cjk_glyphs(stderr: str) -> bool:
    text = str(stderr or "")
    if not text:
        return False
    if "cjk unified ideograph" in text.lower():
        return True
    for match in _GLYPH_MISSING_RE.finditer(text):
        try:
            codepoint = int(match.group(1))
        except Exception:
            continue
        if _is_cjk_codepoint(codepoint):
            return True
    return False


def _extract_actionable_warnings(stderr: str) -> List[str]:
    warnings: List[str] = []
    seen: set[str] = set()
    for raw_line in str(stderr or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if any(pat in lowered for pat in _BENIGN_WARNING_PATTERNS):
            continue
        if ("findfont:" not in lowered) and ("warning" not in lowered):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        warnings.append(line)
    return warnings


def _warning_feedback(warnings: List[str]) -> str:
    if not warnings:
        return ""
    preview = "\n".join(f"- {line}" for line in warnings[:6])
    return (
        "execution_warnings_detected:\n"
        f"{preview}\n"
        "请修复这些 warning 的根因后再输出代码，禁止通过忽略 warning 掩盖问题。"
    )



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


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return None


def chart_agent_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on", "y"}


def chart_agent_engine(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"llm", "opencode", "auto"}:
        return text
    if text:
        return "llm"
    return "llm"


def chart_agent_opencode_overrides(args: Dict[str, Any]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    if not isinstance(args, dict):
        return overrides
    if args.get("opencode_model"):
        overrides["model"] = str(args.get("opencode_model")).strip()
    if args.get("opencode_profile"):
        overrides["profile"] = str(args.get("opencode_profile")).strip()
    if args.get("opencode_mode"):
        overrides["mode"] = str(args.get("opencode_mode")).strip()
    if args.get("opencode_timeout_sec") is not None:
        timeout_val = _int_or_none(args.get("opencode_timeout_sec"))
        if timeout_val is not None:
            overrides["timeout_sec"] = max(10, timeout_val)
    if args.get("opencode_enabled") is not None:
        overrides["enabled"] = chart_agent_bool(args.get("opencode_enabled"), True)
    if args.get("opencode_max_retries") is not None:
        retries_val = _int_or_none(args.get("opencode_max_retries"))
        if retries_val is not None:
            overrides["max_retries"] = max(1, min(retries_val, 6))
    return overrides


def chart_agent_packages(value: Any) -> List[str]:
    out: List[str] = []
    if isinstance(value, str):
        candidates = [x.strip() for x in value.replace(";", ",").split(",")]
    elif isinstance(value, list):
        candidates = [str(x).strip() for x in value]
    else:
        return out
    seen = set()
    for item in candidates:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def chart_agent_extract_python_code(text: str) -> str:
    raw = str(text or "")
    match = re.search(r"```(?:python)?\s*(.*?)```", raw, flags=re.S | re.I)
    if match:
        return str(match.group(1) or "").strip()
    return raw.strip()


def chart_agent_default_code() -> str:
    return (
        "import matplotlib.pyplot as plt\n"
        "data = input_data\n"
        "numeric = {}\n"
        "if isinstance(data, dict):\n"
        "    for k, v in data.items():\n"
        "        if isinstance(v, (int, float)):\n"
        "            numeric[str(k)] = float(v)\n"
        "        elif isinstance(v, dict):\n"
        "            for kk, vv in v.items():\n"
        "                if isinstance(vv, (int, float)):\n"
        "                    numeric[f'{k}.{kk}'] = float(vv)\n"
        "        elif isinstance(v, list):\n"
        "            nums = [x for x in v if isinstance(x, (int, float))]\n"
        "            if nums:\n"
        "                numeric[str(k)] = sum(nums) / len(nums)\n"
        "plt.figure(figsize=(8, 4.8))\n"
        "if numeric:\n"
        "    labels = list(numeric.keys())\n"
        "    values = list(numeric.values())\n"
        "    plt.bar(labels, values, color='#3B82F6', alpha=0.9)\n"
        "    plt.xticks(rotation=20, ha='right')\n"
        "    plt.ylabel('Value')\n"
        "else:\n"
        "    text = str(input_data)[:220]\n"
        "    plt.axis('off')\n"
        "    plt.text(0.5, 0.5, text or 'No numeric input_data found', ha='center', va='center', wrap=True)\n"
        "plt.title('Auto Generated Chart')\n"
        "plt.tight_layout()\n"
        "save_chart()\n"
    )


def chart_agent_generate_candidate(
    task: str,
    input_data: Any,
    last_error: str,
    previous_code: str,
    attempt: int,
    max_retries: int,
    *,
    call_llm: Callable[..., Dict[str, Any]],
    parse_json_from_text: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        payload_text = json.dumps(input_data, ensure_ascii=False)
    except Exception:
        _log.debug("operation failed", exc_info=True)
        payload_text = str(input_data)
    if len(payload_text) > 5000:
        payload_text = payload_text[:5000] + "...[truncated]"

    system = (
        "你是教师端图表代码生成器。输出必须是JSON对象，不要Markdown。\n"
        "必须输出字段：python_code（字符串），packages（字符串数组，可空），summary（字符串）。\n"
        "python_code规则：\n"
        "- 使用 matplotlib（可选 numpy/pandas/seaborn）。\n"
        "- 变量 input_data 已可直接使用。\n"
        "- 必须调用 save_chart('main.png') 或 save_chart()。\n"
        "- 运行时不得产生 warning；若上次出现 warning，必须修复根因而不是忽略。\n"
        "- 代码必须可直接运行，禁止解释文字。"
    )
    user = (
        f"任务描述:\n{task}\n\n"
        f"输入数据(JSON):\n{payload_text}\n\n"
        f"当前重试: {attempt}/{max_retries}\n"
        f"上次错误:\n{last_error or '(none)'}\n\n"
        f"上次代码:\n{previous_code[:3000] if previous_code else '(none)'}\n"
    )
    try:
        resp = call_llm(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            role_hint="teacher",
            kind="chart.agent.codegen",
        )
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        return {"python_code": "", "packages": [], "summary": "", "raw": f"llm_error: {exc}"}

    parsed = parse_json_from_text(content) or {}
    python_code = str(parsed.get("python_code") or "").strip()
    if not python_code:
        python_code = chart_agent_extract_python_code(content)
    packages = chart_agent_packages(parsed.get("packages"))
    summary = str(parsed.get("summary") or "").strip()
    return {"python_code": python_code, "packages": packages, "summary": summary, "raw": content}


def chart_agent_generate_candidate_opencode(
    task: str,
    input_data: Any,
    last_error: str,
    previous_code: str,
    attempt: int,
    max_retries: int,
    opencode_overrides: Dict[str, Any],
    *,
    app_root: Any,
    run_opencode_codegen: Callable[..., Dict[str, Any]],
) -> Dict[str, Any]:
    result = run_opencode_codegen(
        app_root=app_root,
        task=task,
        input_data=input_data,
        last_error=last_error,
        previous_code=previous_code,
        attempt=attempt,
        max_retries=max_retries,
        overrides=opencode_overrides,
    )
    return {
        "python_code": str(result.get("python_code") or "").strip(),
        "packages": chart_agent_packages(result.get("packages")),
        "summary": str(result.get("summary") or "").strip(),
        "raw": result.get("raw") or "",
        "error": result.get("error"),
        "meta": {
            "ok": bool(result.get("ok")),
            "exit_code": result.get("exit_code"),
            "duration_sec": result.get("duration_sec"),
            "stderr": str(result.get("stderr") or "")[:800],
            "command": result.get("command") or [],
        },
    }


def chart_agent_run(args: Dict[str, Any], *, deps: ChartAgentRunDeps) -> Dict[str, Any]:
    task = str(args.get("task") or "").strip()
    if not task:
        return {"error": "task_required"}

    timeout_sec = deps.safe_int_arg(args.get("timeout_sec"), 180, 30, 3600)
    max_retries = deps.safe_int_arg(args.get("max_retries"), 3, 1, 6)
    auto_install = deps.chart_bool(args.get("auto_install"), True)
    requested_engine = deps.chart_engine(args.get("engine"))
    if requested_engine == "opencode":
        return {
            "ok": False,
            "error": "opencode_forbidden",
            "detail": "opencode runtime is disabled at system level",
            "engine_requested": requested_engine,
            "status_code": 400,
        }

    effective_engine = "llm"
    effective_max_retries = max_retries
    chart_hint = str(args.get("chart_hint") or task[:120]).strip()
    save_as = str(args.get("save_as") or "main.png").strip() or "main.png"
    input_data = args.get("input_data")
    requested_packages = deps.chart_packages(args.get("packages"))

    attempts: List[Dict[str, Any]] = []
    last_error = ""
    previous_code = ""
    unresolved_warning_lines: List[str] = []
    unresolved_warning_result: Dict[str, Any] = {}

    for attempt in range(1, effective_max_retries + 1):
        candidate = deps.generate_candidate(
            task,
            input_data,
            last_error,
            previous_code,
            attempt,
            effective_max_retries,
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
                "execution_profile": "sandboxed",
                "_audit_source": "chart.agent.run",
                "_audit_role": "teacher",
            },
            deps.app_root,
            deps.uploads_dir,
        )
        stderr_text = str(exec_res.get("stderr") or "")
        missing_cjk_glyphs = _has_missing_cjk_glyphs(stderr_text)
        warning_lines = _extract_actionable_warnings(stderr_text)
        has_actionable_warnings = bool(warning_lines)
        if _contains_cjk_text(python_code) and missing_cjk_glyphs:
            has_actionable_warnings = True
            if "render_quality_failed: missing_cjk_glyphs" not in warning_lines:
                warning_lines = ["render_quality_failed: missing_cjk_glyphs", *warning_lines]
            if len(warning_lines) == 1:
                warning_lines.append("UserWarning: missing CJK glyphs in selected font.")

        attempts.append(
            {
                "attempt": attempt,
                "engine": effective_engine,
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
                    "stderr": stderr_text[:500],
                    "missing_cjk_glyphs": missing_cjk_glyphs,
                    "warnings": warning_lines[:8],
                    "has_actionable_warnings": has_actionable_warnings,
                },
            }
        )

        if exec_res.get("ok") and exec_res.get("image_url"):
            if has_actionable_warnings:
                unresolved_warning_lines = warning_lines
                unresolved_warning_result = {
                    "run_id": exec_res.get("run_id"),
                    "image_url": exec_res.get("image_url"),
                    "meta_url": exec_res.get("meta_url"),
                    "artifacts": exec_res.get("artifacts") or [],
                }
                previous_code = python_code
                last_error = _warning_feedback(warning_lines)
                continue
            title = str(args.get("title") or "图表结果").strip() or "图表结果"
            markdown = f"### {title}\n\n![{title}]({exec_res.get('image_url')})"
            return {
                "ok": True,
                "task": task,
                "attempt_used": attempt,
                "engine_requested": requested_engine,
                "engine_used": effective_engine,
                "image_url": exec_res.get("image_url"),
                "meta_url": exec_res.get("meta_url"),
                "run_id": exec_res.get("run_id"),
                "artifacts": exec_res.get("artifacts") or [],
                "installed_packages": exec_res.get("installed_packages") or [],
                "python_executable": exec_res.get("python_executable"),
                "markdown": markdown,
                "attempts": attempts,
                "opencode_status": None,
            }

        previous_code = python_code
        last_error = str(exec_res.get("stderr") or exec_res.get("error") or "unknown_error")

    if unresolved_warning_result:
        return {
            "ok": False,
            "error": "chart_agent_unresolved_warnings",
            "task": task,
            "max_retries": effective_max_retries,
            "engine_requested": requested_engine,
            "last_error": (last_error or _warning_feedback(unresolved_warning_lines))[:1200],
            "warnings": unresolved_warning_lines[:8],
            "best_effort_run_id": unresolved_warning_result.get("run_id"),
            "best_effort_image_url": unresolved_warning_result.get("image_url"),
            "best_effort_meta_url": unresolved_warning_result.get("meta_url"),
            "best_effort_artifacts": unresolved_warning_result.get("artifacts") or [],
            "attempts": attempts,
            "opencode_status": None,
        }

    return {
        "ok": False,
        "error": "chart_agent_failed",
        "task": task,
        "max_retries": effective_max_retries,
        "engine_requested": requested_engine,
        "last_error": last_error[:1200],
        "attempts": attempts,
        "opencode_status": None,
    }
