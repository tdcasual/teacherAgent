from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from llm_gateway import UnifiedLLMRequest

import logging
_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatRuntimeDeps:
    gateway: Any
    limit: Callable[[Any], Any]
    default_limiter: Any
    student_limiter: Any
    teacher_limiter: Any
    resolve_teacher_id: Callable[[Optional[str]], str]
    resolve_teacher_model_registry: Callable[[str], Dict[str, Any]]
    resolve_teacher_provider_target: Callable[[str, str, str, str], Optional[Dict[str, Any]]]
    ensure_teacher_routing_file: Callable[[str], Path]
    routing_config_path_for_role: Callable[[Optional[str], Optional[str]], Path]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]
    monotonic: Callable[[], float] = time.monotonic


def call_llm_runtime(
    messages: List[Dict[str, Any]],
    *,
    deps: ChatRuntimeDeps,
    tools: Optional[List[Dict[str, Any]]] = None,
    role_hint: Optional[str] = None,
    max_tokens: Optional[int] = None,
    skill_id: Optional[str] = None,
    kind: Optional[str] = None,
    teacher_id: Optional[str] = None,
    skill_runtime: Optional[Any] = None,
) -> Dict[str, Any]:
    req = UnifiedLLMRequest(messages=messages, tools=tools, tool_choice="auto" if tools else None, max_tokens=max_tokens)
    t0 = deps.monotonic()
    if role_hint == "student":
        limiter = deps.student_limiter
    elif role_hint == "teacher":
        limiter = deps.teacher_limiter
    else:
        limiter = deps.default_limiter

    route_selected = False
    route_reason = ""
    route_rule_id = ""
    route_channel_id = ""
    route_target_provider = ""
    route_target_mode = ""
    route_target_model = ""
    route_source = "gateway_default"
    route_policy_route_id = ""
    route_actor = ""
    route_config_path = ""
    route_exception = ""
    route_policy_exception = ""
    routing_registry: Dict[str, Any] = deps.gateway.registry if isinstance(getattr(deps.gateway, "registry", None), dict) else {}
    if role_hint == "teacher":
        route_actor = deps.resolve_teacher_id(teacher_id)
        route_config_path = str(deps.ensure_teacher_routing_file(route_actor))
        try:
            merged_registry = deps.resolve_teacher_model_registry(route_actor)
            if isinstance(merged_registry, dict):
                routing_registry = merged_registry
        except Exception as exc:
            _log.warning("operation failed", exc_info=True)
            route_exception = str(exc)[:200]
    else:
        route_config_path = str(deps.routing_config_path_for_role(role_hint, teacher_id))
    route_attempt_errors: List[Dict[str, str]] = []
    route_validation_errors: List[str] = []
    route_validation_warnings: List[str] = []

    with deps.limit(limiter):
        result = None
        routing_context: Optional[Any] = None
        try:
            from .llm_routing import RoutingContext, get_compiled_routing, resolve_routing
            routing_context = RoutingContext(
                role=role_hint,
                skill_id=skill_id,
                kind=kind,
                needs_tools=bool(tools),
                needs_json=bool(req.json_schema),
            )
            compiled = get_compiled_routing(Path(route_config_path), routing_registry)
            route_validation_errors = list(compiled.errors)
            route_validation_warnings = list(compiled.warnings)
            decision = resolve_routing(compiled, routing_context)
            route_reason = decision.reason
            route_rule_id = decision.matched_rule_id or ""
            if decision.selected:
                route_selected = True
                for candidate in decision.candidates:
                    route_req = UnifiedLLMRequest(
                        messages=req.messages,
                        input_text=req.input_text,
                        tools=req.tools,
                        tool_choice=req.tool_choice,
                        json_schema=req.json_schema,
                        temperature=candidate.temperature if candidate.temperature is not None else req.temperature,
                        max_tokens=req.max_tokens if req.max_tokens is not None else candidate.max_tokens,
                        stream=req.stream,
                        metadata=dict(req.metadata or {}),
                    )
                    target_override = None
                    if role_hint == "teacher" and route_actor:
                        try:
                            target_override = deps.resolve_teacher_provider_target(
                                route_actor,
                                candidate.provider,
                                candidate.mode,
                                candidate.model,
                            )
                        except Exception as exc:
                            _log.warning("operation failed", exc_info=True)
                            route_attempt_errors.append(
                                {
                                    "source": "teacher_provider_target",
                                    "channel_id": candidate.channel_id,
                                    "error": str(exc)[:200],
                                }
                            )
                    try:
                        if isinstance(target_override, dict):
                            result = deps.gateway.generate(route_req, allow_fallback=False, target_override=target_override)
                        else:
                            result = deps.gateway.generate(
                                route_req,
                                provider=candidate.provider,
                                mode=candidate.mode,
                                model=candidate.model,
                                allow_fallback=False,
                            )
                        route_channel_id = candidate.channel_id
                        route_target_provider = candidate.provider
                        route_target_mode = candidate.mode
                        route_target_model = candidate.model
                        route_source = "teacher_routing"
                        break
                    except Exception as exc:  # pragma: no cover - exercised via integration tests
                        _log.warning("operation failed", exc_info=True)
                        route_attempt_errors.append(
                            {"source": "teacher_routing", "channel_id": candidate.channel_id, "error": str(exc)[:200]}
                        )
        except Exception as exc:  # pragma: no cover - exercised via integration tests
            _log.warning("operation failed", exc_info=True)
            route_exception = str(exc)[:200]

        if result is None and skill_runtime is not None:
            resolver = getattr(skill_runtime, "resolve_model_targets", None)
            if callable(resolver):
                try:
                    policy_targets = resolver(
                        role_hint=role_hint,
                        kind=kind,
                        needs_tools=bool(tools),
                        needs_json=bool(req.json_schema),
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    _log.warning("operation failed", exc_info=True)
                    policy_targets = []
                    route_policy_exception = str(exc)[:200]
                for item in policy_targets or []:
                    provider = str(item.get("provider") or "").strip()
                    mode = str(item.get("mode") or "").strip()
                    model = str(item.get("model") or "").strip()
                    if not provider or not mode or not model:
                        continue
                    policy_route_id = str(item.get("route_id") or "").strip()
                    temperature = item.get("temperature")
                    max_tokens_override = item.get("max_tokens")
                    route_req = UnifiedLLMRequest(
                        messages=req.messages,
                        input_text=req.input_text,
                        tools=req.tools,
                        tool_choice=req.tool_choice,
                        json_schema=req.json_schema,
                        temperature=temperature if temperature is not None else req.temperature,
                        max_tokens=req.max_tokens if req.max_tokens is not None else max_tokens_override,
                        stream=req.stream,
                        metadata=dict(req.metadata or {}),
                    )
                    target_override = None
                    if role_hint == "teacher" and route_actor:
                        try:
                            target_override = deps.resolve_teacher_provider_target(
                                route_actor,
                                provider,
                                mode,
                                model,
                            )
                        except Exception as exc:
                            _log.warning("operation failed", exc_info=True)
                            route_attempt_errors.append(
                                {
                                    "source": "skill_policy_provider_target",
                                    "route_id": policy_route_id or "default",
                                    "error": str(exc)[:200],
                                }
                            )
                    try:
                        if isinstance(target_override, dict):
                            result = deps.gateway.generate(route_req, allow_fallback=False, target_override=target_override)
                        else:
                            result = deps.gateway.generate(
                                route_req,
                                provider=provider,
                                mode=mode,
                                model=model,
                                allow_fallback=False,
                            )
                        route_selected = True
                        route_source = "skill_policy"
                        route_policy_route_id = policy_route_id
                        route_reason = "skill_policy_default" if policy_route_id == "default" else "skill_policy_matched"
                        route_rule_id = ""
                        route_channel_id = f"skill_policy:{policy_route_id or 'default'}"
                        route_target_provider = provider
                        route_target_mode = mode
                        route_target_model = model
                        break
                    except Exception as exc:  # pragma: no cover - defensive
                        _log.warning("operation failed", exc_info=True)
                        route_attempt_errors.append(
                            {
                                "source": "skill_policy",
                                "route_id": policy_route_id or "default",
                                "error": str(exc)[:200],
                            }
                        )

        if result is None:
            if not route_reason:
                route_reason = "gateway_fallback"
            result = deps.gateway.generate(req, allow_fallback=True)

    deps.diag_log(
        "llm.call.done",
        {
            "duration_ms": int((deps.monotonic() - t0) * 1000),
            "role": role_hint or "unknown",
            "skill_id": skill_id or "",
            "kind": kind or "",
            "tools": bool(tools),
            "route_selected": route_selected,
            "route_reason": route_reason,
            "route_rule_id": route_rule_id,
            "route_channel_id": route_channel_id,
            "route_provider": route_target_provider,
            "route_mode": route_target_mode,
            "route_model": route_target_model,
            "route_source": route_source,
            "route_policy_route_id": route_policy_route_id,
            "route_actor": route_actor,
            "route_config_path": route_config_path,
            "route_attempt_errors": route_attempt_errors,
            "route_validation_errors": route_validation_errors[:10],
            "route_validation_warnings": route_validation_warnings[:10],
            "route_exception": route_exception,
            "route_policy_exception": route_policy_exception,
        },
    )
    return result.as_chat_completion()
