from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    _log.debug("yaml package not available, YAML config loading disabled")
    yaml = None


_PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_MAX_STD_CHARS = 60000
_MAX_TIMEOUT_SEC = 3600
_HELP_CACHE_LOCK = threading.Lock()
_HELP_CACHE: Dict[str, Dict[str, bool]] = {}


def _clip_text(value: str) -> str:
    if len(value) <= _MAX_STD_CHARS:
        return value
    return value[:_MAX_STD_CHARS] + "\n...[truncated]..."


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        _log.debug("int conversion failed for value=%r, using default=%d", value, default)
        return default
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


def _normalize_packages(value: Any) -> List[str]:
    raw: List[str] = []
    if isinstance(value, list):
        raw = [str(item or "").strip() for item in value]
    elif isinstance(value, str):
        raw = [item.strip() for item in re.split(r"[,\s;；，]+", value) if item.strip()]
    out: List[str] = []
    seen: set[str] = set()
    for item in raw:
        if not item or not _PACKAGE_RE.fullmatch(item):
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out[:24]


def _parse_json_dict(text: str) -> Optional[Dict[str, Any]]:
    content = str(text or "").strip()
    if not content:
        return None
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n|```$", "", content, flags=re.S).strip()
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception:
        _log.warning("JSON parse failed in _parse_json_dict (full content), len=%d", len(content), exc_info=True)
        pass
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        _log.warning("JSON parse failed in _parse_json_dict (regex match), len=%d", len(match.group(0)), exc_info=True)
        return None
    return data if isinstance(data, dict) else None


def _extract_python_code(text: str) -> str:
    content = str(text or "").strip()
    if not content:
        return ""
    patterns = [
        r"```python\s*(.*?)```",
        r"```py\s*(.*?)```",
        r"```\s*(.*?)```",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.S | re.I)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def _collect_text_from_json_lines(stdout: str) -> str:
    chunks: List[str] = []
    for line in (stdout or "").splitlines():
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith("{") and raw.endswith("}"):
            try:
                payload = json.loads(raw)
            except Exception:
                _log.warning("JSON line parse failed in _collect_text_from_json_lines, line=%s", raw[:200], exc_info=True)
                chunks.append(raw)
                continue
            if isinstance(payload, dict):
                part = payload.get("part")
                if isinstance(part, dict):
                    for key in ("text", "content", "message", "response", "result", "output", "final"):
                        value = part.get(key)
                        if isinstance(value, str) and value.strip():
                            chunks.append(value.strip())
                for key in ("content", "text", "message", "response", "result", "output", "final"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        chunks.append(value.strip())
        else:
            chunks.append(raw)
    return "\n".join(chunks).strip()


def _extract_candidate(stdout: str, stderr: str) -> Dict[str, Any]:
    combined = _collect_text_from_json_lines(stdout)
    if not combined:
        combined = (stdout or "").strip()
    parsed = _parse_json_dict(combined) or {}
    if not parsed:
        for block in reversed([line.strip() for line in combined.splitlines() if line.strip()]):
            candidate = _parse_json_dict(block)
            if isinstance(candidate, dict) and candidate:
                parsed = candidate
                if candidate.get("python_code"):
                    break
    python_code = str(parsed.get("python_code") or "").strip()
    if not python_code:
        python_code = _extract_python_code(combined)
    packages = _normalize_packages(parsed.get("packages"))
    summary = str(parsed.get("summary") or "").strip()
    if not summary:
        summary = str(parsed.get("message") or "").strip()
    return {
        "python_code": python_code,
        "packages": packages,
        "summary": summary,
        "raw": combined or (stdout or "")[:2000] or (stderr or "")[:2000],
    }


def _load_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists() or yaml is None:
        return {}
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("Failed to load config file %s", path, exc_info=True)
        return {}
    if not isinstance(parsed, dict):
        return {}
    nested = parsed.get("opencode_bridge")
    if isinstance(nested, dict):
        return dict(nested)
    return dict(parsed)


def load_opencode_bridge_config(app_root: Path, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config_file_raw = str(os.getenv("OPENCODE_BRIDGE_FILE") or "").strip()
    config_file = Path(config_file_raw).resolve() if config_file_raw else (app_root / "config" / "opencode_bridge.yaml")
    loaded = _load_config_file(config_file)
    merged: Dict[str, Any] = {
        "enabled": False,
        "bin": "opencode",
        "mode": "run",
        "attach_url": "",
        "agent": "chart-builder",
        "model": "",
        "config_path": "",
        "timeout_sec": 180,
        "max_retries": 3,
        "extra_env": {},
    }
    if loaded:
        merged.update(loaded)
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})

    env_map = {
        "OPENCODE_BRIDGE_ENABLED": "enabled",
        "OPENCODE_BRIDGE_BIN": "bin",
        "OPENCODE_BRIDGE_MODE": "mode",
        "OPENCODE_BRIDGE_ATTACH_URL": "attach_url",
        "OPENCODE_BRIDGE_AGENT": "agent",
        "OPENCODE_BRIDGE_MODEL": "model",
        "OPENCODE_BRIDGE_CONFIG_PATH": "config_path",
        "OPENCODE_BRIDGE_TIMEOUT_SEC": "timeout_sec",
        "OPENCODE_BRIDGE_MAX_RETRIES": "max_retries",
    }
    for env_name, key in env_map.items():
        value = os.getenv(env_name)
        if value is not None and str(value).strip() != "":
            merged[key] = value

    extra_env_raw = os.getenv("OPENCODE_BRIDGE_EXTRA_ENV")
    if extra_env_raw:
        try:
            parsed = json.loads(extra_env_raw)
            if isinstance(parsed, dict):
                merged["extra_env"] = parsed
        except Exception:
            _log.warning("Failed to parse OPENCODE_BRIDGE_EXTRA_ENV=%s", extra_env_raw[:200], exc_info=True)
            pass

    mode = str(merged.get("mode") or "run").strip().lower()
    if mode not in {"run", "attach"}:
        mode = "run"

    extra_env_value = merged.get("extra_env")
    extra_env: Dict[str, str] = {}
    if isinstance(extra_env_value, dict):
        for key, value in extra_env_value.items():
            key_text = str(key or "").strip()
            if not key_text:
                continue
            extra_env[key_text] = str(value if value is not None else "")

    normalized = {
        "enabled": _as_bool(merged.get("enabled"), False),
        "bin": str(merged.get("bin") or "opencode").strip() or "opencode",
        "mode": mode,
        "attach_url": str(merged.get("attach_url") or "").strip(),
        "agent": str(merged.get("agent") or "").strip(),
        "model": str(merged.get("model") or "").strip(),
        "config_path": str(merged.get("config_path") or "").strip(),
        "timeout_sec": _as_int(merged.get("timeout_sec"), 180, 30, _MAX_TIMEOUT_SEC),
        "max_retries": _as_int(merged.get("max_retries"), 3, 1, 6),
        "extra_env": extra_env,
        "config_file": str(config_file),
    }
    return normalized


def resolve_opencode_status(app_root: Path, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = load_opencode_bridge_config(app_root, overrides=overrides)
    binary_config = str(config.get("bin") or "opencode").strip()
    if not config.get("enabled"):
        return {
            "enabled": False,
            "available": False,
            "reason": "disabled",
            "binary": None,
            "config": config,
        }

    binary_path: Optional[str]
    if Path(binary_config).is_absolute():
        binary_path = str(Path(binary_config)) if Path(binary_config).exists() else None
    else:
        binary_path = shutil.which(binary_config)
    if not binary_path:
        return {
            "enabled": True,
            "available": False,
            "reason": "binary_not_found",
            "binary": None,
            "config": config,
        }
    return {
        "enabled": True,
        "available": True,
        "reason": "ok",
        "binary": binary_path,
        "config": config,
    }


def _detect_run_flags(binary: str, timeout_sec: int = 15) -> Dict[str, bool]:
    key = str(binary)
    with _HELP_CACHE_LOCK:
        cached = _HELP_CACHE.get(key)
    if cached is not None:
        return dict(cached)

    flags = {
        "format": False,
        "agent": False,
        "model": False,
        "config": False,
        "attach": False,
        "prompt": False,
    }
    try:
        proc = subprocess.run(
            [binary, "run", "--help"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        help_text = f"{proc.stdout or ''}\n{proc.stderr or ''}".lower()
        flags["format"] = "--format" in help_text
        flags["agent"] = "--agent" in help_text
        flags["model"] = "--model" in help_text
        flags["config"] = "--config" in help_text
        flags["attach"] = "--attach" in help_text
        flags["prompt"] = ("--prompt" in help_text) or bool(re.search(r"(^|\s)-p(,|\s)", help_text))
    except Exception:
        _log.warning("Failed to detect run flags for binary=%s", binary, exc_info=True)
        pass

    with _HELP_CACHE_LOCK:
        _HELP_CACHE[key] = dict(flags)
    return flags


def build_opencode_chart_prompt(
    task: str,
    input_data: Any,
    last_error: str,
    previous_code: str,
    attempt: int,
    max_retries: int,
) -> str:
    try:
        payload_text = json.dumps(input_data, ensure_ascii=False)
    except Exception:
        _log.debug("json.dumps failed for input_data, falling back to str()")
        payload_text = str(input_data)
    if len(payload_text) > 5000:
        payload_text = payload_text[:5000] + "...[truncated]"

    previous_preview = previous_code[:3000] if previous_code else "(none)"
    error_text = last_error or "(none)"
    return (
        "你是教师端图表编程代理。只输出一个JSON对象，不要Markdown，不要解释。\n"
        "JSON字段必须包含：python_code(字符串), packages(字符串数组), summary(字符串)。\n"
        "python_code 规则：\n"
        "- 可使用 matplotlib/numpy/pandas/seaborn。\n"
        "- 可以直接访问变量 input_data。\n"
        "- 必须调用 save_chart('main.png') 或 save_chart()。\n"
        "- 代码必须可直接运行。\n\n"
        f"任务描述:\n{task}\n\n"
        f"输入数据(JSON):\n{payload_text}\n\n"
        f"当前重试: {attempt}/{max_retries}\n"
        f"上次错误:\n{error_text}\n\n"
        f"上次代码:\n{previous_preview}\n"
    )


def run_opencode_codegen(
    *,
    app_root: Path,
    task: str,
    input_data: Any,
    last_error: str,
    previous_code: str,
    attempt: int,
    max_retries: int,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    status = resolve_opencode_status(app_root, overrides=overrides)
    if not status.get("enabled"):
        return {"ok": False, "error": "opencode_disabled", "status": status}
    if not status.get("available"):
        return {"ok": False, "error": "opencode_unavailable", "status": status}

    binary = str(status.get("binary") or "")
    config = status.get("config") or {}
    flags = _detect_run_flags(binary)
    timeout_sec = _as_int(config.get("timeout_sec"), 180, 30, _MAX_TIMEOUT_SEC)
    prompt = build_opencode_chart_prompt(
        task=task,
        input_data=input_data,
        last_error=last_error,
        previous_code=previous_code,
        attempt=attempt,
        max_retries=max_retries,
    )

    cmd: List[str] = [binary, "run"]
    if flags.get("format"):
        cmd.extend(["--format", "json"])

    model = str(config.get("model") or "").strip()
    if model and flags.get("model"):
        cmd.extend(["--model", model])

    agent = str(config.get("agent") or "").strip()
    if agent and flags.get("agent"):
        cmd.extend(["--agent", agent])

    config_path = str(config.get("config_path") or "").strip()
    if config_path and flags.get("config"):
        cmd.extend(["--config", config_path])

    if str(config.get("mode") or "run") == "attach":
        attach_url = str(config.get("attach_url") or "").strip()
        if attach_url and flags.get("attach"):
            cmd.extend(["--attach", attach_url])

    if flags.get("prompt"):
        cmd.extend(["--prompt", prompt])
    else:
        cmd.append(prompt)

    env = os.environ.copy()
    extra_env = config.get("extra_env") if isinstance(config, dict) else {}
    if isinstance(extra_env, dict):
        for key, value in extra_env.items():
            key_text = str(key or "").strip()
            if not key_text:
                continue
            env[key_text] = str(value if value is not None else "")

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(app_root),
            env=env,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return {
            "ok": False,
            "error": "opencode_timeout",
            "timeout_sec": timeout_sec,
            "duration_sec": round(time.monotonic() - t0, 3),
            "stdout": _clip_text(stdout),
            "stderr": _clip_text((stderr + "\nopencode timed out").strip()),
            "command": cmd,
            "status": status,
        }
    except Exception as exc:
        _log.warning("opencode subprocess execution failed: %s", exc, exc_info=True)
        return {
            "ok": False,
            "error": "opencode_exec_error",
            "detail": str(exc),
            "duration_sec": round(time.monotonic() - t0, 3),
            "command": cmd,
            "status": status,
        }

    stdout = _clip_text(proc.stdout or "")
    stderr = _clip_text(proc.stderr or "")
    candidate = _extract_candidate(stdout, stderr)
    python_code = str(candidate.get("python_code") or "").strip()
    return {
        "ok": proc.returncode == 0 and bool(python_code),
        "exit_code": int(proc.returncode),
        "duration_sec": round(time.monotonic() - t0, 3),
        "python_code": python_code,
        "packages": _normalize_packages(candidate.get("packages")),
        "summary": str(candidate.get("summary") or "").strip(),
        "raw": str(candidate.get("raw") or "")[:5000],
        "stdout": stdout,
        "stderr": stderr,
        "command": cmd,
        "flags": flags,
        "status": status,
    }
