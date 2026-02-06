from __future__ import annotations

import json
import re
import threading
import uuid
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


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


@dataclass(frozen=True)
class RoutingContext:
    role: Optional[str] = None
    skill_id: Optional[str] = None
    kind: Optional[str] = None
    needs_tools: bool = False
    needs_json: bool = False


@dataclass(frozen=True)
class RouteCandidate:
    channel_id: str
    provider: str
    mode: str
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    capabilities: Dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "provider": self.provider,
            "mode": self.mode,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "capabilities": dict(self.capabilities),
        }


@dataclass(frozen=True)
class RoutingDecision:
    enabled: bool
    matched_rule_id: Optional[str]
    candidates: List[RouteCandidate]
    reason: str

    @property
    def selected(self) -> bool:
        return len(self.candidates) > 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "matched_rule_id": self.matched_rule_id,
            "reason": self.reason,
            "selected": self.selected,
            "candidates": [c.as_dict() for c in self.candidates],
        }


@dataclass(frozen=True)
class CompiledRouting:
    config: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    channels_by_id: Dict[str, Dict[str, Any]]
    rules: List[Dict[str, Any]]


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


def _rule_matches(rule: Dict[str, Any], ctx: RoutingContext) -> bool:
    if not _as_bool(rule.get("enabled"), True):
        return False
    match = rule.get("match") if isinstance(rule.get("match"), dict) else {}
    roles = set(_as_str_list(match.get("roles")))
    skills = set(_as_str_list(match.get("skills")))
    kinds = set(_as_str_list(match.get("kinds")))
    needs_tools = match.get("needs_tools")
    needs_json = match.get("needs_json")

    if roles and (ctx.role or "") not in roles:
        return False
    if skills and (ctx.skill_id or "") not in skills:
        return False
    if kinds and (ctx.kind or "") not in kinds:
        return False
    if needs_tools is not None and bool(needs_tools) != bool(ctx.needs_tools):
        return False
    if needs_json is not None and bool(needs_json) != bool(ctx.needs_json):
        return False
    return True


def _channel_capable(channel: Dict[str, Any], ctx: RoutingContext) -> bool:
    cap = channel.get("capabilities") if isinstance(channel.get("capabilities"), dict) else {}
    tools_ok = _as_bool(cap.get("tools"), True)
    json_ok = _as_bool(cap.get("json"), True)
    if ctx.needs_tools and not tools_ok:
        return False
    if ctx.needs_json and not json_ok:
        return False
    return True


def _expand_candidate_chain(
    channels_by_id: Dict[str, Dict[str, Any]],
    start_channel_id: str,
    ctx: RoutingContext,
) -> List[RouteCandidate]:
    out: List[RouteCandidate] = []
    queue: List[str] = [start_channel_id]
    seen: set[str] = set()
    while queue:
        channel_id = queue.pop(0)
        if channel_id in seen:
            continue
        seen.add(channel_id)
        channel = channels_by_id.get(channel_id)
        if not channel:
            continue
        for fb in channel.get("fallback_channels") or []:
            if fb not in seen:
                queue.append(fb)
        if not _channel_capable(channel, ctx):
            continue
        target = channel.get("target") if isinstance(channel.get("target"), dict) else {}
        params = channel.get("params") if isinstance(channel.get("params"), dict) else {}
        cap = channel.get("capabilities") if isinstance(channel.get("capabilities"), dict) else {}
        out.append(
            RouteCandidate(
                channel_id=channel_id,
                provider=_as_str(target.get("provider")),
                mode=_as_str(target.get("mode")),
                model=_as_str(target.get("model")),
                temperature=_as_float_opt(params.get("temperature")),
                max_tokens=_as_int_opt(params.get("max_tokens")),
                capabilities={"tools": _as_bool(cap.get("tools"), True), "json": _as_bool(cap.get("json"), True)},
            )
        )
    return out


def resolve_routing(compiled: CompiledRouting, ctx: RoutingContext) -> RoutingDecision:
    enabled = _as_bool(compiled.config.get("enabled"), False)
    if not enabled:
        return RoutingDecision(enabled=False, matched_rule_id=None, candidates=[], reason="routing_disabled")
    if compiled.errors:
        return RoutingDecision(enabled=True, matched_rule_id=None, candidates=[], reason="routing_invalid")

    matched_rule_id: Optional[str] = None
    for rule in compiled.rules:
        if not _rule_matches(rule, ctx):
            continue
        matched_rule_id = _as_str(rule.get("id")) or None
        route = rule.get("route") if isinstance(rule.get("route"), dict) else {}
        channel_id = _as_str(route.get("channel_id"))
        if not channel_id:
            continue
        candidates = _expand_candidate_chain(compiled.channels_by_id, channel_id, ctx)
        if candidates:
            return RoutingDecision(enabled=True, matched_rule_id=matched_rule_id, candidates=candidates, reason="matched")
    if matched_rule_id:
        return RoutingDecision(enabled=True, matched_rule_id=matched_rule_id, candidates=[], reason="no_capable_channel")
    return RoutingDecision(enabled=True, matched_rule_id=None, candidates=[], reason="no_rule_matched")


def simulate_routing(compiled: CompiledRouting, ctx: RoutingContext) -> Dict[str, Any]:
    decision = resolve_routing(compiled, ctx)
    return {
        "context": {
            "role": ctx.role,
            "skill_id": ctx.skill_id,
            "kind": ctx.kind,
            "needs_tools": ctx.needs_tools,
            "needs_json": ctx.needs_json,
        },
        "decision": decision.as_dict(),
        "validation": {"errors": list(compiled.errors), "warnings": list(compiled.warnings)},
    }


def _history_dir(config_path: Path) -> Path:
    return config_path.parent / "llm_routing_history"


def _proposals_dir(config_path: Path) -> Path:
    return config_path.parent / "llm_routing_proposals"


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


def create_routing_proposal(
    config_path: Path,
    model_registry: Dict[str, Any],
    config_payload: Dict[str, Any],
    actor: str,
    note: str = "",
) -> Dict[str, Any]:
    validation = validate_routing_config(config_payload, model_registry)
    proposal_id = _safe_id("proposal")
    proposal = {
        "proposal_id": proposal_id,
        "created_at": _now_iso(),
        "created_by": actor or "unknown",
        "status": "pending",
        "note": note or "",
        "candidate": validation.get("normalized") if validation.get("ok") else (config_payload or {}),
        "validation": {
            "ok": bool(validation.get("ok")),
            "errors": validation.get("errors") or [],
            "warnings": validation.get("warnings") or [],
        },
    }
    proposals_dir = _proposals_dir(config_path)
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / f"{proposal_id}.json"
    _atomic_write_json(path, proposal)
    return {
        "ok": True,
        "proposal_id": proposal_id,
        "status": "pending",
        "validation": proposal["validation"],
        "proposal_path": str(path),
    }


def _proposal_path(config_path: Path, proposal_id: str) -> Path:
    return _proposals_dir(config_path) / f"{proposal_id}.json"


def apply_routing_proposal(
    config_path: Path,
    model_registry: Dict[str, Any],
    proposal_id: str,
    approve: bool,
    actor: str,
) -> Dict[str, Any]:
    proposal_id = _as_str(proposal_id)
    if not proposal_id:
        return {"ok": False, "error": "proposal_id_required"}
    lock = _config_lock(config_path)
    with lock:
        path = _proposal_path(config_path, proposal_id)
        proposal = _read_json(path)
        if not proposal:
            return {"ok": False, "error": "proposal_not_found", "proposal_id": proposal_id}
        if _as_str(proposal.get("status")) in {"applied", "rejected"}:
            return {"ok": False, "error": "proposal_already_reviewed", "proposal_id": proposal_id}

        proposal["reviewed_at"] = _now_iso()
        proposal["reviewed_by"] = actor or "unknown"
        if not approve:
            proposal["status"] = "rejected"
            _atomic_write_json(path, proposal)
            return {"ok": True, "proposal_id": proposal_id, "status": "rejected"}

        candidate = proposal.get("candidate") if isinstance(proposal.get("candidate"), dict) else {}
        apply_res = apply_routing_config(
            config_path=config_path,
            model_registry=model_registry,
            config_payload=candidate,
            actor=actor,
            source=f"proposal:{proposal_id}",
            note=_as_str(proposal.get("note")),
        )
        if not apply_res.get("ok"):
            proposal["status"] = "failed"
            proposal["apply_error"] = apply_res
            _atomic_write_json(path, proposal)
            return {"ok": False, "proposal_id": proposal_id, "status": "failed", "error": apply_res}

        proposal["status"] = "applied"
        proposal["applied_version"] = apply_res.get("version")
        proposal["history_path"] = apply_res.get("history_path")
        _atomic_write_json(path, proposal)
        return {
            "ok": True,
            "proposal_id": proposal_id,
            "status": "applied",
            "version": apply_res.get("version"),
            "history_path": apply_res.get("history_path"),
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


def read_proposal(config_path: Path, proposal_id: str) -> Dict[str, Any]:
    path = _proposal_path(config_path, _as_str(proposal_id))
    data = _read_json(path)
    if not data:
        return {"ok": False, "error": "proposal_not_found", "proposal_id": proposal_id}
    return {"ok": True, "proposal": data, "proposal_path": str(path)}


def list_proposals(config_path: Path, limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
    base = _proposals_dir(config_path)
    if not base.exists():
        return []
    items: List[Dict[str, Any]] = []
    for path in base.glob("*.json"):
        data = _read_json(path)
        row = {
            "proposal_id": _as_str(data.get("proposal_id")) or path.stem,
            "created_at": _as_str(data.get("created_at")),
            "created_by": _as_str(data.get("created_by")),
            "status": _as_str(data.get("status")) or "pending",
            "note": _as_str(data.get("note")),
            "validation_ok": bool(((data.get("validation") or {}).get("ok"))),
            "proposal_path": str(path),
        }
        if status and row["status"] != status:
            continue
        items.append(row)
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    take = max(1, min(int(limit), 200))
    return items[:take]
