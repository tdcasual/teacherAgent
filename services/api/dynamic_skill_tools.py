from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - defensive
    yaml = None

from services.common.tool_registry import DEFAULT_TOOL_REGISTRY, ToolDef, ToolRegistry

_log = logging.getLogger(__name__)

_MANIFEST_CANDIDATES = ("tool-manifest.yaml", "tool-manifest.yml")
_TOOLS_ARTIFACT = "dynamic_tools.json"
_TOOLS_LOCK = "dynamic_tools.lock.json"
_TOOLS_REPORT = "dynamic_tools.report.json"
_MAX_STD_CHARS = 60000
_DEFAULT_TIMEOUT_SEC = 20
_MAX_TIMEOUT_SEC = 600
_DEFAULT_RETRY_ATTEMPTS = 3
_MAX_RETRY_ATTEMPTS = 6
_DEFAULT_RETRY_BACKOFF_MS = 300
_MAX_RETRY_BACKOFF_MS = 5000
_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,100}$")
_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)(?:\|default:([^}]+))?\s*\}\}")

_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Tuple[str, Dict[str, Dict[str, Any]]]] = {}


def _clip_text(value: str) -> str:
    if len(value) <= _MAX_STD_CHARS:
        return value
    return value[:_MAX_STD_CHARS] + "\n...[truncated]..."


def _normalize_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except Exception:
        return _DEFAULT_TIMEOUT_SEC
    if timeout <= 0:
        return _DEFAULT_TIMEOUT_SEC
    if timeout > _MAX_TIMEOUT_SEC:
        return _MAX_TIMEOUT_SEC
    return timeout


def _normalize_retry(value: Any) -> Dict[str, int]:
    raw = value if isinstance(value, dict) else {}
    try:
        attempts = int(raw.get("max_attempts", _DEFAULT_RETRY_ATTEMPTS))
    except Exception:
        attempts = _DEFAULT_RETRY_ATTEMPTS
    try:
        backoff_ms = int(raw.get("backoff_ms", _DEFAULT_RETRY_BACKOFF_MS))
    except Exception:
        backoff_ms = _DEFAULT_RETRY_BACKOFF_MS
    attempts = max(1, min(_MAX_RETRY_ATTEMPTS, attempts))
    backoff_ms = max(0, min(_MAX_RETRY_BACKOFF_MS, backoff_ms))
    return {"max_attempts": attempts, "backoff_ms": backoff_ms}


def _resolve_inside(base: Path, relpath: str) -> Path:
    rel = Path(str(relpath or "").strip())
    if rel.is_absolute():
        raise ValueError(f"absolute path is not allowed: {relpath}")
    resolved_base = base.resolve()
    resolved_target = (base / rel).resolve()
    if resolved_target == resolved_base or resolved_base not in resolved_target.parents:
        raise ValueError(f"path traversal detected: {relpath}")
    return resolved_target


def _discover_manifest_paths(skill_dir: Path) -> List[Path]:
    found: List[Path] = []
    for name in _MANIFEST_CANDIDATES:
        path = skill_dir / name
        if path.exists() and path.is_file():
            found.append(path)
            break
    tools_dir = skill_dir / "tools"
    if tools_dir.exists() and tools_dir.is_dir():
        for path in sorted(tools_dir.glob("*.y*ml")):
            if not path.is_file():
                continue
            if path.name in _MANIFEST_CANDIDATES:
                continue
            found.append(path)
    return found


def _read_yaml(path: Path) -> Any:
    if yaml is None:
        raise ValueError("yaml parser unavailable")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"YAML parse failed: {exc}") from exc


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _render_token(expr: str, default_value: Optional[str], args: Dict[str, Any], context: Dict[str, Any]) -> str:
    def _lookup(path: str) -> Tuple[Any, bool]:
        parts = [p for p in path.split(".") if p]
        if not parts:
            return None, False
        root = parts[0]
        cur: Any
        if root == "args":
            cur = args
        elif root == "context":
            cur = context
        else:
            return None, False
        for part in parts[1:]:
            if isinstance(cur, dict) and part in cur:
                cur = cur.get(part)
                continue
            return None, False
        return cur, True

    value, ok = _lookup(expr)
    if not ok or value is None or value == "":
        fallback = str(default_value or "").strip()
        if fallback.startswith(("'", '"')) and fallback.endswith(("'", '"')) and len(fallback) >= 2:
            fallback = fallback[1:-1]
        return fallback
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _render_string(template: str, args: Dict[str, Any], context: Dict[str, Any]) -> str:
    text = str(template or "")

    def _replace(match: re.Match[str]) -> str:
        expr = str(match.group(1) or "").strip()
        default_value = match.group(2)
        return _render_token(expr, default_value, args, context)

    return _TEMPLATE_RE.sub(_replace, text)


def _render_value(value: Any, args: Dict[str, Any], context: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _render_string(value, args, context)
    if isinstance(value, list):
        return [_render_value(v, args, context) for v in value]
    if isinstance(value, dict):
        return {str(k): _render_value(v, args, context) for k, v in value.items()}
    return value


def _normalize_tool_spec(
    item: Dict[str, Any],
    *,
    skill_dir: Path,
    default_timeout_sec: int,
    default_retry: Dict[str, int],
) -> Dict[str, Any]:
    name = _as_str(item.get("name"))
    if not name or not _TOOL_NAME_RE.fullmatch(name):
        raise ValueError(f"invalid tool name: {name!r}")
    description = _as_str(item.get("description")) or name
    input_schema = item.get("input_schema")
    if not isinstance(input_schema, dict):
        input_schema = item.get("parameters")
    if not isinstance(input_schema, dict):
        input_schema = {"type": "object", "properties": {}, "additionalProperties": True}

    executor = _as_dict(item.get("executor"))
    if not executor:
        # Alias compatibility for common external formats.
        if item.get("entry") or item.get("script"):
            executor = {
                "type": "script",
                "entry": item.get("entry") or item.get("script"),
                "args_template": item.get("args_template") or item.get("args") or [],
            }
        elif item.get("url") or item.get("endpoint"):
            executor = {
                "type": "http",
                "method": item.get("method") or "POST",
                "url": item.get("url") or item.get("endpoint"),
                "headers_template": item.get("headers_template") or item.get("headers") or {},
                "body_template": item.get("body_template") or item.get("body") or {},
            }
    exec_type = _as_str(executor.get("type")).lower()
    if exec_type not in {"script", "http"}:
        raise ValueError(f"unsupported executor type: {exec_type or '<empty>'}")

    timeout_sec = _normalize_timeout(executor.get("timeout_sec", item.get("timeout_sec", default_timeout_sec)))
    retry = _normalize_retry(executor.get("retry", item.get("retry", default_retry)))
    normalized_executor: Dict[str, Any] = {"type": exec_type, "timeout_sec": timeout_sec, "retry": retry}

    if exec_type == "script":
        entry = _as_str(executor.get("entry") or executor.get("script"))
        if not entry:
            raise ValueError("script executor requires entry")
        entry_path = _resolve_inside(skill_dir, entry)
        if not entry_path.exists() or not entry_path.is_file():
            raise ValueError(f"script entry not found: {entry}")
        args_template = executor.get("args_template")
        if not isinstance(args_template, list):
            args_template = executor.get("args")
        args_list = [str(x) for x in _as_list(args_template)]
        stdin_template = executor.get("stdin_template")
        normalized_executor.update(
            {
                "entry": entry_path.name if entry_path.parent == skill_dir else str(entry_path.relative_to(skill_dir)),
                "args_template": args_list,
                "stdin_template": stdin_template,
            }
        )
    else:
        method = _as_str(executor.get("method") or "POST").upper()
        url = _as_str(executor.get("url") or executor.get("endpoint"))
        if not url:
            raise ValueError("http executor requires url")
        headers_template = _as_dict(executor.get("headers_template") or executor.get("headers"))
        body_template = executor.get("body_template")
        if body_template is None and "body" in executor:
            body_template = executor.get("body")
        normalized_executor.update(
            {
                "method": method,
                "url": url,
                "headers_template": headers_template,
                "body_template": body_template if body_template is not None else {},
            }
        )

    return {
        "name": name,
        "description": description,
        "input_schema": input_schema,
        "executor": normalized_executor,
    }


def _collect_manifest_tools(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = _read_yaml(path)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)], {}
    if isinstance(parsed, dict):
        tools = parsed.get("tools")
        if isinstance(tools, list):
            return [item for item in tools if isinstance(item, dict)], parsed
        # Allow one-file-one-tool style.
        if parsed.get("name") and (parsed.get("executor") or parsed.get("script") or parsed.get("endpoint") or parsed.get("url")):
            return [parsed], {}
    return [], {}


def _hash_paths(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted([p.resolve() for p in paths], key=lambda p: str(p)):
        digest.update(str(path).encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except Exception:
            _log.debug("file read failed for hash path=%s", path, exc_info=True)
            digest.update(b"<read-failed>")
    return digest.hexdigest()


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def compile_skill_dynamic_tools(skill_dir: Path) -> Dict[str, Any]:
    skill_root = skill_dir.resolve()
    manifests = _discover_manifest_paths(skill_root)
    base: Dict[str, Any] = {
        "ok": True,
        "skill_dir": str(skill_root),
        "source_files": [str(path) for path in manifests],
        "tools": [],
        "invalid": [],
        "shadowed": [],
        "compiled_ok": 0,
        "invalid_count": 0,
        "shadowed_count": 0,
        "manifest_hash": "",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if not manifests:
        base["manifest_hash"] = ""
        return base

    static_names = set(DEFAULT_TOOL_REGISTRY.names())
    default_timeout_sec = _DEFAULT_TIMEOUT_SEC
    default_retry = _normalize_retry({})
    tools_raw: List[Dict[str, Any]] = []

    for idx, manifest in enumerate(manifests):
        try:
            collected, root = _collect_manifest_tools(manifest)
        except Exception as exc:
            base["invalid"].append({"source": str(manifest), "error": str(exc)})
            continue
        if idx == 0 and root:
            runtime = _as_dict(root.get("runtime"))
            default_timeout_sec = _normalize_timeout(runtime.get("default_timeout_sec", _DEFAULT_TIMEOUT_SEC))
            default_retry = _normalize_retry(runtime.get("default_retry"))
        for item in collected:
            item_copy = dict(item)
            item_copy["__source"] = str(manifest)
            tools_raw.append(item_copy)

    seen_names: set[str] = set()
    compiled: List[Dict[str, Any]] = []
    for item in tools_raw:
        source = _as_str(item.pop("__source"))
        try:
            spec = _normalize_tool_spec(
                item,
                skill_dir=skill_root,
                default_timeout_sec=default_timeout_sec,
                default_retry=default_retry,
            )
            name = str(spec.get("name") or "")
            if name in seen_names:
                raise ValueError(f"duplicate tool name: {name}")
            seen_names.add(name)
            if name in static_names:
                base["shadowed"].append({"name": name, "reason": "conflicts_with_static_tool", "source": source})
                continue
            spec["skill_dir"] = str(skill_root)
            compiled.append(spec)
        except Exception as exc:
            base["invalid"].append({"source": source, "name": item.get("name"), "error": str(exc)})

    manifest_hash = _hash_paths(manifests)
    base["tools"] = compiled
    base["compiled_ok"] = len(compiled)
    base["invalid_count"] = len(base["invalid"])
    base["shadowed_count"] = len(base["shadowed"])
    base["manifest_hash"] = manifest_hash

    artifacts_path = skill_root / _TOOLS_ARTIFACT
    lock_path = skill_root / _TOOLS_LOCK
    report_path = skill_root / _TOOLS_REPORT
    try:
        _write_json(artifacts_path, {"tools": compiled, "manifest_hash": manifest_hash, "updated_at": base["updated_at"]})
        _write_json(
            lock_path,
            {
                "manifest_hash": manifest_hash,
                "source_files": [str(path) for path in manifests],
                "compiled_ok": len(compiled),
                "updated_at": base["updated_at"],
            },
        )
        _write_json(
            report_path,
            {
                "compiled_ok": len(compiled),
                "invalid": base["invalid"],
                "shadowed": base["shadowed"],
                "updated_at": base["updated_at"],
            },
        )
    except Exception:
        _log.warning("failed to write dynamic tool artifacts for %s", skill_root, exc_info=True)

    return base


def _load_compiled_tools(skill_dir: Path) -> Tuple[str, Dict[str, Dict[str, Any]]]:
    manifests = _discover_manifest_paths(skill_dir)
    if not manifests:
        return "", {}
    manifest_hash = _hash_paths(manifests)
    key = str(skill_dir.resolve())
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == manifest_hash:
            return cached[0], dict(cached[1])

    compiled = compile_skill_dynamic_tools(skill_dir)
    tools_raw = compiled.get("tools")
    tools: List[Any] = tools_raw if isinstance(tools_raw, list) else []
    by_name: Dict[str, Dict[str, Any]] = {}
    for item in tools:
        if not isinstance(item, dict):
            continue
        name = _as_str(item.get("name"))
        if not name:
            continue
        by_name[name] = item
    with _CACHE_LOCK:
        _CACHE[key] = (manifest_hash, dict(by_name))
    return manifest_hash, by_name


def load_dynamic_tools_for_skill_source(source_path: str) -> Dict[str, Dict[str, Any]]:
    source = Path(str(source_path or "")).resolve()
    skill_dir = source.parent
    _, tools = _load_compiled_tools(skill_dir)
    return tools


def clear_dynamic_tools_cache(skill_dir: Optional[Path] = None) -> None:
    with _CACHE_LOCK:
        if skill_dir is None:
            _CACHE.clear()
            return
        _CACHE.pop(str(skill_dir.resolve()), None)


def build_dynamic_openai_tools(
    allowed: Iterable[str],
    dynamic_tools: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for name in sorted(set(str(x) for x in allowed)):
        spec = dynamic_tools.get(name)
        if not isinstance(spec, dict):
            continue
        schema = spec.get("input_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}, "additionalProperties": True}
        description = _as_str(spec.get("description")) or name
        out.append(ToolDef(name=name, description=description, parameters=schema).to_openai())
    return out


def validate_dynamic_arguments(name: str, spec: Dict[str, Any], args: Any) -> List[str]:
    schema = spec.get("input_schema")
    if not isinstance(schema, dict):
        schema = {"type": "object", "properties": {}, "additionalProperties": True}
    registry = ToolRegistry({name: ToolDef(name=name, description=_as_str(spec.get("description")), parameters=schema)})
    return registry.validate_arguments(name, args)


def _execute_script_tool(spec: Dict[str, Any], args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    exec_cfg = _as_dict(spec.get("executor"))
    skill_dir = Path(_as_str(spec.get("skill_dir"))).resolve()
    entry_rel = _as_str(exec_cfg.get("entry"))
    entry_path = _resolve_inside(skill_dir, entry_rel)
    args_template = _as_list(exec_cfg.get("args_template"))
    rendered_args = [_render_string(str(item), args, context) for item in args_template]
    cmd: List[str]
    if entry_path.suffix.lower() == ".py":
        cmd = [sys.executable, str(entry_path)]
    else:
        cmd = [str(entry_path)]
    cmd.extend(rendered_args)
    stdin_template = exec_cfg.get("stdin_template")
    stdin_data = None
    if stdin_template is not None:
        rendered = _render_value(stdin_template, args, context)
        stdin_data = json.dumps(rendered, ensure_ascii=False)
    timeout_sec = _normalize_timeout(exec_cfg.get("timeout_sec"))
    proc = subprocess.run(
        cmd,
        cwd=str(skill_dir),
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    stdout = _clip_text(proc.stdout or "")
    stderr = _clip_text(proc.stderr or "")
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"script exited with code {proc.returncode}",
            "stdout": stdout,
            "stderr": stderr,
            "returncode": proc.returncode,
        }
    payload = (proc.stdout or "").strip()
    if payload:
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                if "ok" in parsed:
                    return parsed
                return {"ok": True, "data": parsed, "stdout": stdout}
            return {"ok": True, "data": parsed, "stdout": stdout}
        except Exception:
            _log.debug("script output is not JSON", exc_info=True)
    return {"ok": True, "data": {"stdout": stdout}}


def _execute_http_tool(spec: Dict[str, Any], args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    exec_cfg = _as_dict(spec.get("executor"))
    method = _as_str(exec_cfg.get("method") or "POST").upper()
    url = _render_string(_as_str(exec_cfg.get("url")), args, context)
    headers_template = _as_dict(exec_cfg.get("headers_template"))
    headers = {str(k): str(_render_value(v, args, context)) for k, v in headers_template.items()}
    body_template = exec_cfg.get("body_template")
    body_rendered = _render_value(body_template, args, context)
    body_bytes: Optional[bytes] = None
    if body_rendered is not None:
        if isinstance(body_rendered, (dict, list)):
            body_text = json.dumps(body_rendered, ensure_ascii=False)
            body_bytes = body_text.encode("utf-8")
            headers.setdefault("Content-Type", "application/json; charset=utf-8")
        else:
            body_text = str(body_rendered)
            body_bytes = body_text.encode("utf-8")
    timeout_sec = _normalize_timeout(exec_cfg.get("timeout_sec"))
    request = urllib.request.Request(url=url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as resp:
            raw = resp.read(2 * 1024 * 1024)
            text = raw.decode("utf-8", errors="replace")
            content_type = str(resp.headers.get("Content-Type") or "").lower()
            if "json" in content_type:
                try:
                    payload = json.loads(text)
                except Exception:
                    _log.debug("http response json parse failed", exc_info=True)
                    payload = {"raw": _clip_text(text)}
            else:
                try:
                    payload = json.loads(text)
                except Exception:
                    payload = {"raw": _clip_text(text)}
            return {"ok": True, "status": int(getattr(resp, "status", 200) or 200), "data": payload}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            _log.debug("http error body read failed", exc_info=True)
        return {"ok": False, "error": f"http error {exc.code}", "status": int(exc.code), "body": _clip_text(body)}
    except Exception as exc:
        return {"ok": False, "error": f"http request failed: {exc}"}


def dispatch_dynamic_tool(
    *,
    name: str,
    args: Dict[str, Any],
    role: Optional[str],
    skill_id: Optional[str],
    teacher_id: Optional[str],
    teacher_skills_dir: Path,
    diag_log: Optional[Callable[[str, Optional[Dict[str, Any]]], None]] = None,
) -> Optional[Dict[str, Any]]:
    # Scope decision: only teacher role in production chain.
    if role != "teacher":
        return None
    skill_name = _as_str(skill_id)
    if not skill_name:
        return None
    try:
        skill_dir = _resolve_inside(teacher_skills_dir.resolve(), skill_name)
    except Exception:
        return None
    if not skill_dir.exists() or not skill_dir.is_dir():
        return None
    _, dynamic_tools = _load_compiled_tools(skill_dir)
    spec = dynamic_tools.get(name)
    if not isinstance(spec, dict):
        return None

    issues = validate_dynamic_arguments(name, spec, args)
    if issues:
        return {"error": "invalid_arguments", "tool": name, "issues": issues[:20], "_dynamic_tool": True}

    exec_cfg = _as_dict(spec.get("executor"))
    retry = _normalize_retry(exec_cfg.get("retry"))
    attempts = int(retry.get("max_attempts", _DEFAULT_RETRY_ATTEMPTS))
    backoff_ms = int(retry.get("backoff_ms", _DEFAULT_RETRY_BACKOFF_MS))
    context = {"teacher_id": _as_str(teacher_id), "skill_id": skill_name}
    last_result: Dict[str, Any] = {"ok": False, "error": "dynamic tool execution failed"}
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        if _as_str(exec_cfg.get("type")) == "script":
            result = _execute_script_tool(spec, args, context)
        else:
            result = _execute_http_tool(spec, args, context)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if callable(diag_log):
            diag_log(
                "dynamic_tool.call",
                {
                    "skill_id": skill_name,
                    "tool_name": name,
                    "attempt": attempt,
                    "executor": _as_str(exec_cfg.get("type")),
                    "latency_ms": elapsed_ms,
                    "ok": bool(result.get("ok")),
                },
            )
        if bool(result.get("ok")):
            if isinstance(result, dict):
                result["_dynamic_tool"] = True
            return result
        last_result = result if isinstance(result, dict) else {"ok": False, "error": str(result)}
        if attempt < attempts and backoff_ms > 0:
            time.sleep((backoff_ms * (2 ** (attempt - 1))) / 1000.0)

    degraded: Dict[str, Any] = {
        "error": "dynamic_tool_failed_after_retries",
        "tool": name,
        "attempts": attempts,
        "detail": _as_str(last_result.get("error") or "dynamic tool execution failed"),
        "_dynamic_tool": True,
        "_dynamic_tool_degraded": True,
    }
    if callable(diag_log):
        diag_log(
            "dynamic_tool.degraded",
            {"skill_id": skill_name, "tool_name": name, "attempts": attempts, "error": degraded["detail"]},
        )
    return degraded
