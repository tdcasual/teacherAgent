from __future__ import annotations

import json
import os
import re
import threading
import uuid
import hashlib
import importlib as _importlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import llm_routing_resolver as _llm_routing_resolver_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_llm_routing_resolver_module)
from .llm_routing_resolver import *  # noqa: F401,F403
from .llm_routing_resolver import CompiledRouting, RoutingContext  # explicit for type hints

from . import llm_routing_proposals as _llm_routing_proposals_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_llm_routing_proposals_module)
from .llm_routing_proposals import *  # noqa: F401,F403


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,80}$")
_KIND_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,120}$")
_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Tuple[Tuple[int, int, int, str, Tuple[Tuple[str, str], ...]], "CompiledRouting"]] = {}
_CONFIG_LOCKS_LOCK = threading.Lock()
_CONFIG_LOCKS: Dict[str, threading.RLock] = {}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_id(prefix: str = "rt") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(value: Any, default: int, min_value: Optional[int] = None) -> int:
    try:
        iv = int(value)
    except Exception:
        iv = default
    if min_value is not None and iv < min_value:
        iv = min_value
    return iv


def _as_float_opt(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _as_int_opt(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = _as_str(item)
        if text:
            out.append(text)
    return out


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def default_routing_config() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "enabled": False,
        "version": 1,
        "updated_at": _now_iso(),
        "updated_by": "system",
        "channels": [],
        "rules": [],
    }


def _model_registry_signature(model_registry: Dict[str, Any]) -> Tuple[Tuple[str, str], ...]:
    providers = model_registry.get("providers") if isinstance(model_registry.get("providers"), dict) else {}
    pairs: List[Tuple[str, str]] = []
    for provider, provider_cfg in providers.items():
        if not isinstance(provider_cfg, dict):
            continue
        modes = provider_cfg.get("modes") if isinstance(provider_cfg.get("modes"), dict) else {}
        for mode in modes.keys():
            pairs.append((str(provider), str(mode)))
    return tuple(sorted(pairs))


def _config_lock(config_path: Path) -> threading.RLock:
    key = str(config_path.resolve())
    with _CONFIG_LOCKS_LOCK:
        lock = _CONFIG_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _CONFIG_LOCKS[key] = lock
        return lock


def _allowed_provider_modes(model_registry: Dict[str, Any]) -> set[Tuple[str, str]]:
    return set(_model_registry_signature(model_registry))


def _normalize_channels(
    channels_raw: Any,
    allowed_pairs: set[Tuple[str, str]],
    errors: List[str],
    warnings: List[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    channels: List[Dict[str, Any]] = []
    by_id: Dict[str, Dict[str, Any]] = {}
    raw_items = channels_raw if isinstance(channels_raw, list) else []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            warnings.append(f"channels[{idx}] ignored: not an object")
            continue
        channel_id = _as_str(item.get("id"))
        if not channel_id or not _ID_RE.match(channel_id):
            errors.append(f"channels[{idx}].id invalid")
            continue
        if channel_id in by_id:
            errors.append(f"channel id duplicated: {channel_id}")
            continue

        target_raw = item.get("target") if isinstance(item.get("target"), dict) else {}
        provider = _as_str(target_raw.get("provider"))
        mode = _as_str(target_raw.get("mode"))
        model = _as_str(target_raw.get("model"))
        if not provider or not mode:
            errors.append(f"channel {channel_id}: target.provider/mode required")
            continue
        if (provider, mode) not in allowed_pairs:
            errors.append(f"channel {channel_id}: target provider/mode not allowed: {provider}/{mode}")
            continue
        if not model:
            errors.append(f"channel {channel_id}: target.model required")
            continue

        params_raw = item.get("params") if isinstance(item.get("params"), dict) else {}
        temperature = _as_float_opt(params_raw.get("temperature"))
        max_tokens = _as_int_opt(params_raw.get("max_tokens"))
        if temperature is not None:
            if temperature < 0 or temperature > 2:
                errors.append(f"channel {channel_id}: params.temperature must be in [0,2]")
                continue
        if max_tokens is not None and max_tokens <= 0:
            errors.append(f"channel {channel_id}: params.max_tokens must be > 0")
            continue

        capabilities_raw = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
        capabilities = {
            "tools": _as_bool(capabilities_raw.get("tools"), True),
            "json": _as_bool(capabilities_raw.get("json"), True),
        }

        fallback_channels: List[str] = []
        for fb in _as_str_list(item.get("fallback_channels")):
            if not _ID_RE.match(fb):
                warnings.append(f"channel {channel_id}: ignored invalid fallback channel id: {fb}")
                continue
            fallback_channels.append(fb)

        channel = {
            "id": channel_id,
            "title": _as_str(item.get("title")) or channel_id,
            "target": {"provider": provider, "mode": mode, "model": model},
            "params": {"temperature": temperature, "max_tokens": max_tokens},
            "fallback_channels": fallback_channels,
            "capabilities": capabilities,
        }
        channels.append(channel)
        by_id[channel_id] = channel

    return channels, by_id


def _contains_path(graph: Dict[str, Dict[str, Any]], start: str, target: str, seen: set[str]) -> bool:
    if start == target:
        return True
    if start in seen:
        return False
    seen.add(start)
    node = graph.get(start)
    if not node:
        return False
    for nxt in node.get("fallback_channels") or []:
        if _contains_path(graph, nxt, target, seen):
            return True
    return False


def _sanitize_fallback_graph(
    channels_by_id: Dict[str, Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
) -> None:
    for channel_id, channel in channels_by_id.items():
        sanitized: List[str] = []
        for fb in channel.get("fallback_channels") or []:
            if fb not in channels_by_id:
                warnings.append(f"channel {channel_id}: fallback channel not found: {fb}")
                continue
            if fb == channel_id:
                errors.append(f"channel {channel_id}: fallback cannot reference itself")
                continue
            if _contains_path(channels_by_id, fb, channel_id, set()):
                errors.append(f"channel {channel_id}: fallback cycle detected via {fb}")
                continue
            if fb not in sanitized:
                sanitized.append(fb)
        channel["fallback_channels"] = sanitized


def _normalize_rules(
    rules_raw: Any,
    channels_by_id: Dict[str, Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    raw_items = rules_raw if isinstance(rules_raw, list) else []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            warnings.append(f"rules[{idx}] ignored: not an object")
            continue
        rule_id = _as_str(item.get("id")) or f"rule_{idx + 1}"
        if not _ID_RE.match(rule_id):
            errors.append(f"rules[{idx}].id invalid")
            continue
        if rule_id in seen_ids:
            errors.append(f"rule id duplicated: {rule_id}")
            continue
        seen_ids.add(rule_id)

        route_raw = item.get("route") if isinstance(item.get("route"), dict) else {}
        channel_id = _as_str(route_raw.get("channel_id"))
        if not channel_id:
            errors.append(f"rule {rule_id}: route.channel_id required")
            continue
        if channel_id not in channels_by_id:
            errors.append(f"rule {rule_id}: route.channel_id not found: {channel_id}")
            continue

        match_raw = item.get("match") if isinstance(item.get("match"), dict) else {}
        roles = [x for x in _as_str_list(match_raw.get("roles")) if _ID_RE.match(x)]
        skills = [x for x in _as_str_list(match_raw.get("skills")) if _ID_RE.match(x)]
        kinds = [x for x in _as_str_list(match_raw.get("kinds")) if _KIND_RE.match(x)]
        needs_tools_val = match_raw.get("needs_tools")
        if needs_tools_val is None:
            needs_tools_val = match_raw.get("with_tools")
        needs_json_val = match_raw.get("needs_json")
        if needs_json_val is None:
            needs_json_val = match_raw.get("with_json")
        needs_tools = None if needs_tools_val is None else _as_bool(needs_tools_val, False)
        needs_json = None if needs_json_val is None else _as_bool(needs_json_val, False)

        priority = _as_int(item.get("priority"), 100, min_value=0)
        rule = {
            "id": rule_id,
            "priority": priority,
            "enabled": _as_bool(item.get("enabled"), True),
            "match": {
                "roles": roles,
                "skills": skills,
                "kinds": kinds,
                "needs_tools": needs_tools,
                "needs_json": needs_json,
            },
            "route": {"channel_id": channel_id},
        }
        rules.append(rule)
    rules.sort(key=lambda r: (-int(r.get("priority") or 0), str(r.get("id") or "")))
    return rules


def validate_routing_config(config_payload: Dict[str, Any], model_registry: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    raw = config_payload if isinstance(config_payload, dict) else {}
    allowed_pairs = _allowed_provider_modes(model_registry)

    channels, channels_by_id = _normalize_channels(raw.get("channels"), allowed_pairs, errors, warnings)
    _sanitize_fallback_graph(channels_by_id, errors, warnings)
    rules = _normalize_rules(raw.get("rules"), channels_by_id, errors, warnings)

    normalized = {
        "schema_version": _as_int(raw.get("schema_version"), 1, min_value=1),
        "enabled": _as_bool(raw.get("enabled"), True),
        "version": _as_int(raw.get("version"), 1, min_value=1),
        "updated_at": _as_str(raw.get("updated_at")) or _now_iso(),
        "updated_by": _as_str(raw.get("updated_by")) or "unknown",
        "channels": sorted(channels, key=lambda c: c["id"]),
        "rules": rules,
    }
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "normalized": normalized}


def _config_signature(config_path: Path, model_registry: Dict[str, Any]) -> Tuple[int, int, int, str, Tuple[Tuple[str, str], ...]]:
    try:
        stat = config_path.stat()
        mtime_ns = int(stat.st_mtime_ns)
        size = int(stat.st_size)
        ctime_ns = int(stat.st_ctime_ns)
        digest = hashlib.sha1(config_path.read_bytes()).hexdigest()
    except Exception:
        mtime_ns = 0
        size = 0
        ctime_ns = 0
        digest = ""
    return (mtime_ns, size, ctime_ns, digest, _model_registry_signature(model_registry))


def _compile_raw_config(config_path: Path, model_registry: Dict[str, Any]) -> CompiledRouting:
    raw = _read_json(config_path)
    if not raw:
        raw = default_routing_config()
    result = validate_routing_config(raw, model_registry)
    normalized = result["normalized"]
    channels_by_id: Dict[str, Dict[str, Any]] = {c["id"]: c for c in normalized.get("channels") or []}
    rules: List[Dict[str, Any]] = normalized.get("rules") or []
    return CompiledRouting(
        config=normalized,
        errors=list(result.get("errors") or []),
        warnings=list(result.get("warnings") or []),
        channels_by_id=channels_by_id,
        rules=rules,
    )


def invalidate_routing_cache(config_path: Path) -> None:
    key = str(config_path.resolve())
    with _CACHE_LOCK:
        _CACHE.pop(key, None)


def get_compiled_routing(config_path: Path, model_registry: Dict[str, Any]) -> CompiledRouting:
    key = str(config_path.resolve())
    signature = _config_signature(config_path, model_registry)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == signature:
            return cached[1]
    compiled = _compile_raw_config(config_path, model_registry)
    with _CACHE_LOCK:
        _CACHE[key] = (signature, compiled)
    return compiled


def _history_dir(config_path: Path) -> Path:
    return config_path.parent / "llm_routing_history"


def _write_history(config_path: Path, payload: Dict[str, Any], actor: str, source: str, note: str = "") -> Path:
    history_dir = _history_dir(config_path)
    history_dir.mkdir(parents=True, exist_ok=True)
    cfg = payload if isinstance(payload, dict) else {}
    version = _as_int(cfg.get("version"), 1, min_value=1)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    history_path = history_dir / f"v{version}_{stamp}_{_safe_id('h')}.json"
    snapshot = {
        "saved_at": _now_iso(),
        "saved_by": actor or "unknown",
        "source": source,
        "note": note or "",
        "config": cfg,
    }
    _atomic_write_json(history_path, snapshot)
    return history_path


def list_routing_history(config_path: Path, limit: int = 20) -> List[Dict[str, Any]]:
    base = _history_dir(config_path)
    if not base.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for path in base.glob("*.json"):
        data = _read_json(path)
        cfg = data.get("config") if isinstance(data.get("config"), dict) else {}
        rows.append(
            {
                "file": str(path),
                "version": _as_int(cfg.get("version"), 1, min_value=1),
                "saved_at": _as_str(data.get("saved_at")),
                "saved_by": _as_str(data.get("saved_by")),
                "source": _as_str(data.get("source")),
                "note": _as_str(data.get("note")),
            }
        )
    rows.sort(key=lambda x: (x.get("version") or 0, x.get("saved_at") or ""), reverse=True)
    take = max(1, min(int(limit), 200))
    return rows[:take]


def get_active_routing(config_path: Path, model_registry: Dict[str, Any]) -> Dict[str, Any]:
    compiled = get_compiled_routing(config_path, model_registry)
    return {
        "config_path": str(config_path),
        "config": compiled.config,
        "validation": {"errors": list(compiled.errors), "warnings": list(compiled.warnings)},
        "history": list_routing_history(config_path, limit=20),
    }


def apply_routing_config(
    config_path: Path,
    model_registry: Dict[str, Any],
    config_payload: Dict[str, Any],
    actor: str,
    source: str = "direct",
    note: str = "",
) -> Dict[str, Any]:
    result = validate_routing_config(config_payload, model_registry)
    if not result.get("ok"):
        return {"ok": False, "errors": result.get("errors") or [], "warnings": result.get("warnings") or []}

    lock = _config_lock(config_path)
    with lock:
        existing = _read_json(config_path)
        current_version = _as_int(existing.get("version"), 0, min_value=0)
        normalized = dict(result.get("normalized") or {})
        normalized["version"] = current_version + 1
        normalized["updated_at"] = _now_iso()
        normalized["updated_by"] = actor or "unknown"

        _atomic_write_json(config_path, normalized)
        history_path = _write_history(config_path, normalized, actor=actor, source=source, note=note)
        invalidate_routing_cache(config_path)
    return {
        "ok": True,
        "version": normalized["version"],
        "config_path": str(config_path),
        "history_path": str(history_path),
        "warnings": result.get("warnings") or [],
    }


def rollback_routing_config(
    config_path: Path,
    model_registry: Dict[str, Any],
    target_version: Any,
    actor: str,
    note: str = "",
) -> Dict[str, Any]:
    try:
        target = int(target_version)
    except Exception:
        return {"ok": False, "error": "invalid_target_version"}
    if target <= 0:
        return {"ok": False, "error": "invalid_target_version"}

    lock = _config_lock(config_path)
    with lock:
        history_dir = _history_dir(config_path)
        if not history_dir.exists():
            return {"ok": False, "error": "history_not_found"}

        chosen: Optional[Dict[str, Any]] = None
        for path in history_dir.glob("*.json"):
            data = _read_json(path)
            cfg = data.get("config") if isinstance(data.get("config"), dict) else {}
            ver = _as_int(cfg.get("version"), 0, min_value=0)
            if ver == target:
                if chosen is None:
                    chosen = {"path": path, "data": data}
                    continue
                prev_time = _as_str((chosen.get("data") or {}).get("saved_at"))
                cur_time = _as_str(data.get("saved_at"))
                if cur_time > prev_time:
                    chosen = {"path": path, "data": data}
        if not chosen:
            return {"ok": False, "error": "target_version_not_found", "target_version": target}

        cfg = chosen["data"].get("config") if isinstance(chosen["data"].get("config"), dict) else {}
        restored = dict(cfg)
        restored["restored_from_version"] = target
        restore_note = note or f"rollback to version {target}"
        return apply_routing_config(
            config_path=config_path,
            model_registry=model_registry,
            config_payload=restored,
            actor=actor,
            source=f"rollback:{target}",
            note=restore_note,
        )


def ensure_routing_file(config_path: Path, actor: str = "system") -> Dict[str, Any]:
    if config_path.exists():
        return {"ok": True, "created": False, "config_path": str(config_path)}
    payload = default_routing_config()
    payload["updated_by"] = actor
    _atomic_write_json(config_path, payload)
    invalidate_routing_cache(config_path)
    return {"ok": True, "created": True, "config_path": str(config_path)}
