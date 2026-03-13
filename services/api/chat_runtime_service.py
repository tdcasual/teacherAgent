from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from llm_gateway import UnifiedLLMRequest

from .role_runtime_policy import get_role_runtime_policy

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatRuntimeDeps:
    gateway: Any
    limit: Callable[[Any], Any]
    default_limiter: Any
    student_limiter: Any
    teacher_limiter: Any
    resolve_teacher_id: Callable[[Optional[str]], str]
    resolve_teacher_model_config: Callable[[str], Dict[str, Any]]
    resolve_teacher_provider_target: Callable[[str, str, str, str], Optional[Dict[str, Any]]]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]
    monotonic: Callable[[], float] = time.monotonic


@dataclass
class ChatRuntimeRouteState:
    selected: bool = False
    reason: str = "gateway_fallback"
    target_provider: str = ""
    target_mode: str = ""
    target_model: str = ""
    source: str = "gateway_default"
    actor: str = ""
    attempt_errors: List[Dict[str, str]] = field(default_factory=list)


def _runtime_limiter(policy: Any, *, deps: ChatRuntimeDeps) -> Any:
    if policy.limiter_kind == "student":
        return deps.student_limiter
    if policy.limiter_kind == "teacher":
        return deps.teacher_limiter
    return deps.default_limiter


def _gateway_generate(
    request: UnifiedLLMRequest,
    *,
    deps: ChatRuntimeDeps,
    stream: bool,
    token_sink: Optional[Callable[[str], None]],
    provider: Optional[str] = None,
    mode: Optional[str] = None,
    model: Optional[str] = None,
    allow_fallback: bool,
    target_override: Optional[Dict[str, Any]] = None,
) -> Any:
    base_kwargs: Dict[str, Any] = {
        "provider": provider,
        "mode": mode,
        "model": model,
        "allow_fallback": allow_fallback,
        "target_override": target_override,
    }
    if bool(stream) and callable(token_sink):
        base_kwargs["token_sink"] = token_sink
    return deps.gateway.generate(request, **base_kwargs)


def _load_teacher_model_config(
    route_actor: str,
    *,
    deps: ChatRuntimeDeps,
    state: ChatRuntimeRouteState,
) -> Dict[str, Any]:
    try:
        return deps.resolve_teacher_model_config(route_actor) or {}
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("operation failed", exc_info=True)
        state.attempt_errors.append({"source": "teacher_model_config", "error": str(exc)[:200]})
        return {}


def _conversation_route_target(config_payload: Dict[str, Any]) -> tuple[str, str, str]:
    models = config_payload.get("models") if isinstance(config_payload, dict) else {}
    conversation = models.get("conversation") if isinstance(models, dict) else {}
    provider = str((conversation or {}).get("provider") or "").strip()
    mode = str((conversation or {}).get("mode") or "").strip()
    model = str((conversation or {}).get("model") or "").strip()
    return provider, mode, model


def _resolve_teacher_target_override(
    route_actor: str,
    *,
    provider: str,
    mode: str,
    model: str,
    deps: ChatRuntimeDeps,
    state: ChatRuntimeRouteState,
) -> Optional[Dict[str, Any]]:
    try:
        return deps.resolve_teacher_provider_target(route_actor, provider, mode, model)
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("operation failed", exc_info=True)
        state.attempt_errors.append(
            {
                "source": "teacher_provider_target",
                "provider": provider,
                "mode": mode,
                "model": model,
                "error": str(exc)[:200],
            }
        )
        return None


def _try_teacher_routed_generate(
    request: UnifiedLLMRequest,
    *,
    provider: str,
    mode: str,
    model: str,
    target_override: Optional[Dict[str, Any]],
    deps: ChatRuntimeDeps,
    stream: bool,
    token_sink: Optional[Callable[[str], None]],
    state: ChatRuntimeRouteState,
) -> Optional[Any]:
    try:
        if isinstance(target_override, dict):
            return _gateway_generate(
                request,
                deps=deps,
                stream=stream,
                token_sink=token_sink,
                allow_fallback=False,
                target_override=target_override,
            )
        return _gateway_generate(
            request,
            deps=deps,
            stream=stream,
            token_sink=token_sink,
            provider=provider,
            mode=mode,
            model=model,
            allow_fallback=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("operation failed", exc_info=True)
        state.attempt_errors.append(
            {
                "source": "teacher_model_config",
                "provider": provider,
                "mode": mode,
                "model": model,
                "error": str(exc)[:200],
            }
        )
        return None


def _attempt_teacher_route(
    request: UnifiedLLMRequest,
    *,
    teacher_id: Optional[str],
    deps: ChatRuntimeDeps,
    stream: bool,
    token_sink: Optional[Callable[[str], None]],
) -> tuple[Optional[Any], ChatRuntimeRouteState]:
    state = ChatRuntimeRouteState(actor=deps.resolve_teacher_id(teacher_id))
    config_payload = _load_teacher_model_config(state.actor, deps=deps, state=state)
    provider, mode, model = _conversation_route_target(config_payload)
    if not (provider and mode and model):
        return None, state
    target_override = _resolve_teacher_target_override(
        state.actor,
        provider=provider,
        mode=mode,
        model=model,
        deps=deps,
        state=state,
    )
    result = _try_teacher_routed_generate(
        request,
        provider=provider,
        mode=mode,
        model=model,
        target_override=target_override,
        deps=deps,
        stream=stream,
        token_sink=token_sink,
        state=state,
    )
    if result is None:
        return None, state
    state.selected = True
    state.reason = "teacher_model_config"
    state.source = "teacher_model_config"
    state.target_provider = provider
    state.target_mode = mode
    state.target_model = model
    return result, state


def _diag_payload(
    *,
    deps: ChatRuntimeDeps,
    started_at: float,
    role_hint: Optional[str],
    skill_id: Optional[str],
    kind: Optional[str],
    tools: Optional[List[Dict[str, Any]]],
    stream: bool,
    state: ChatRuntimeRouteState,
) -> Dict[str, Any]:
    return {
        "duration_ms": int((deps.monotonic() - started_at) * 1000),
        "role": role_hint or "unknown",
        "skill_id": skill_id or "",
        "kind": kind or "",
        "tools": bool(tools),
        "stream": bool(stream),
        "route_selected": state.selected,
        "route_reason": state.reason,
        "route_provider": state.target_provider,
        "route_mode": state.target_mode,
        "route_model": state.target_model,
        "route_source": state.source,
        "route_actor": state.actor,
        "route_attempt_errors": state.attempt_errors,
    }


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
    stream: bool = False,
    token_sink: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    req = UnifiedLLMRequest(
        messages=messages,
        tools=tools,
        tool_choice="auto" if tools else None,
        max_tokens=max_tokens,
        stream=bool(stream),
    )
    t0 = deps.monotonic()
    policy = get_role_runtime_policy(role_hint)
    limiter = _runtime_limiter(policy, deps=deps)
    state = ChatRuntimeRouteState()
    with deps.limit(limiter):
        result = None
        if policy.uses_teacher_model_config:
            result, state = _attempt_teacher_route(
                req,
                teacher_id=teacher_id,
                deps=deps,
                stream=stream,
                token_sink=token_sink,
            )
        if result is None:
            result = _gateway_generate(
                req,
                deps=deps,
                stream=stream,
                token_sink=token_sink,
                allow_fallback=True,
            )

    deps.diag_log("llm.call.done", _diag_payload(
        deps=deps,
        started_at=t0,
        role_hint=role_hint,
        skill_id=skill_id,
        kind=kind,
        tools=tools,
        stream=stream,
        state=state,
    ))
    return result.as_chat_completion()
