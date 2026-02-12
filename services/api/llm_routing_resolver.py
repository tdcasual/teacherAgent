"""LLM routing resolver — dataclasses and routing resolution logic.

Extracted from llm_routing.py. Contains pure routing resolution logic
with no module-level state or file I/O.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


__all__ = [
    "RoutingContext",
    "RouteCandidate",
    "RoutingDecision",
    "CompiledRouting",
    "resolve_routing",
    "simulate_routing",
]


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


def _as_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


def _as_float_opt(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return None


def _as_int_opt(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return None


def _kind_matches(rule_kinds: set[str], context_kind: str) -> bool:
    if not rule_kinds:
        return True
    kind = _as_str(context_kind)
    if not kind:
        return False
    for rule_kind in rule_kinds:
        if kind == rule_kind:
            return True
        if kind.startswith(f"{rule_kind}."):
            return True
    return False


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


def _rule_matches(rule: Dict[str, Any], ctx: RoutingContext) -> bool:
    if not _as_bool(rule.get("enabled"), True):
        return False
    match = _as_dict(rule.get("match"))
    roles = set(_as_str_list(match.get("roles")))
    skills = set(_as_str_list(match.get("skills")))
    kinds = set(_as_str_list(match.get("kinds")))
    needs_tools = match.get("needs_tools")
    needs_json = match.get("needs_json")

    if roles and (ctx.role or "") not in roles:
        return False
    if skills and (ctx.skill_id or "") not in skills:
        return False
    if kinds and not _kind_matches(kinds, ctx.kind or ""):
        return False
    if needs_tools is not None and bool(needs_tools) != bool(ctx.needs_tools):
        return False
    if needs_json is not None and bool(needs_json) != bool(ctx.needs_json):
        return False
    return True


def _channel_capable(channel: Dict[str, Any], ctx: RoutingContext) -> bool:
    cap = _as_dict(channel.get("capabilities"))
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
        target = _as_dict(channel.get("target"))
        params = _as_dict(channel.get("params"))
        cap = _as_dict(channel.get("capabilities"))
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
        route = _as_dict(rule.get("route"))
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
