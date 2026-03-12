from __future__ import annotations

import logging
import time
from dataclasses import dataclass
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
    if policy.limiter_kind == "student":
        limiter = deps.student_limiter
    elif policy.limiter_kind == "teacher":
        limiter = deps.teacher_limiter
    else:
        limiter = deps.default_limiter

    route_selected = False
    route_reason = "gateway_fallback"
    route_target_provider = ""
    route_target_mode = ""
    route_target_model = ""
    route_source = "gateway_default"
    route_actor = ""
    route_attempt_errors: List[Dict[str, str]] = []

    def _gateway_generate(
        request: UnifiedLLMRequest,
        *,
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

    with deps.limit(limiter):
        result = None
        if policy.uses_teacher_model_config:
            route_actor = deps.resolve_teacher_id(teacher_id)
            try:
                config_payload = deps.resolve_teacher_model_config(route_actor) or {}
            except Exception as exc:  # pragma: no cover - defensive
                _log.warning("operation failed", exc_info=True)
                config_payload = {}
                route_attempt_errors.append({"source": "teacher_model_config", "error": str(exc)[:200]})

            models = config_payload.get("models") if isinstance(config_payload, dict) else {}
            conversation = models.get("conversation") if isinstance(models, dict) else {}
            provider = str((conversation or {}).get("provider") or "").strip()
            mode = str((conversation or {}).get("mode") or "").strip()
            model = str((conversation or {}).get("model") or "").strip()
            if provider and mode and model:
                target_override = None
                try:
                    target_override = deps.resolve_teacher_provider_target(route_actor, provider, mode, model)
                except Exception as exc:  # pragma: no cover - defensive
                    _log.warning("operation failed", exc_info=True)
                    route_attempt_errors.append(
                        {
                            "source": "teacher_provider_target",
                            "provider": provider,
                            "mode": mode,
                            "model": model,
                            "error": str(exc)[:200],
                        }
                    )
                try:
                    if isinstance(target_override, dict):
                        result = _gateway_generate(req, allow_fallback=False, target_override=target_override)
                    else:
                        result = _gateway_generate(
                            req,
                            provider=provider,
                            mode=mode,
                            model=model,
                            allow_fallback=False,
                        )
                    route_selected = True
                    route_reason = "teacher_model_config"
                    route_source = "teacher_model_config"
                    route_target_provider = provider
                    route_target_mode = mode
                    route_target_model = model
                except Exception as exc:  # pragma: no cover - defensive
                    _log.warning("operation failed", exc_info=True)
                    route_attempt_errors.append(
                        {
                            "source": "teacher_model_config",
                            "provider": provider,
                            "mode": mode,
                            "model": model,
                            "error": str(exc)[:200],
                        }
                    )

        if result is None:
            result = _gateway_generate(req, allow_fallback=True)

    deps.diag_log(
        "llm.call.done",
        {
            "duration_ms": int((deps.monotonic() - t0) * 1000),
            "role": role_hint or "unknown",
            "skill_id": skill_id or "",
            "kind": kind or "",
            "tools": bool(tools),
            "stream": bool(stream),
            "route_selected": route_selected,
            "route_reason": route_reason,
            "route_provider": route_target_provider,
            "route_mode": route_target_mode,
            "route_model": route_target_model,
            "route_source": route_source,
            "route_actor": route_actor,
            "route_attempt_errors": route_attempt_errors,
        },
    )
    return result.as_chat_completion()
