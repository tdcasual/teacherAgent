from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .teacher_provider_registry_service import _catalog as _provider_catalog_from_registry


@dataclass(frozen=True)
class TeacherLlmRoutingDeps:
    model_registry: Dict[str, Any]
    resolve_model_registry: Callable[[str], Dict[str, Any]]
    resolve_teacher_id: Callable[[Optional[str]], str]
    teacher_llm_routing_path: Callable[[str], Path]
    legacy_routing_path: Path
    atomic_write_json: Callable[[Path, Dict[str, Any]], None]
    now_iso: Callable[[], str]


def _registry_for_actor(actor: str, *, deps: TeacherLlmRoutingDeps) -> Dict[str, Any]:
    try:
        merged = deps.resolve_model_registry(actor)
    except Exception:
        merged = None
    if isinstance(merged, dict):
        return merged
    if isinstance(deps.model_registry, dict):
        return deps.model_registry
    return {}


def llm_routing_catalog(*, deps: TeacherLlmRoutingDeps, actor: Optional[str] = None) -> Dict[str, Any]:
    registry = _registry_for_actor(actor, deps=deps) if actor else deps.model_registry
    return _provider_catalog_from_registry(registry if isinstance(registry, dict) else {})


def routing_actor_from_teacher_id(teacher_id: Optional[str], *, deps: TeacherLlmRoutingDeps) -> str:
    return deps.resolve_teacher_id(teacher_id)


def ensure_teacher_routing_file(actor: str, *, deps: TeacherLlmRoutingDeps) -> Path:
    from .llm_routing import ensure_routing_file

    config_path = deps.teacher_llm_routing_path(actor)
    if not config_path.exists() and deps.legacy_routing_path.exists():
        try:
            legacy = json.loads(deps.legacy_routing_path.read_text(encoding="utf-8"))
            if isinstance(legacy, dict):
                legacy.setdefault("schema_version", 1)
                legacy["updated_at"] = deps.now_iso()
                legacy["updated_by"] = actor
                deps.atomic_write_json(config_path, legacy)
        except Exception:
            pass
    ensure_routing_file(config_path, actor=actor)
    return config_path


def teacher_llm_routing_get(args: Dict[str, Any], *, deps: TeacherLlmRoutingDeps) -> Dict[str, Any]:
    from .llm_routing import get_active_routing, list_proposals

    actor = routing_actor_from_teacher_id(args.get("teacher_id"), deps=deps)
    config_path = ensure_teacher_routing_file(actor, deps=deps)
    registry = _registry_for_actor(actor, deps=deps)
    overview = get_active_routing(config_path, registry)
    history_limit = max(1, min(int(args.get("history_limit", 20) or 20), 200))
    proposal_limit = max(1, min(int(args.get("proposal_limit", 20) or 20), 200))
    proposal_status = str(args.get("proposal_status") or "").strip() or None
    history = overview.get("history") or []
    proposals = list_proposals(config_path, limit=proposal_limit, status=proposal_status)
    return {
        "ok": True,
        "teacher_id": actor,
        "routing": overview.get("config") or {},
        "validation": overview.get("validation") or {},
        "history": history[:history_limit],
        "proposals": proposals,
        "catalog": llm_routing_catalog(deps=deps, actor=actor),
        "config_path": str(config_path),
    }


def teacher_llm_routing_simulate(args: Dict[str, Any], *, deps: TeacherLlmRoutingDeps) -> Dict[str, Any]:
    from .llm_routing import (
        CompiledRouting,
        RoutingContext,
        get_compiled_routing,
        simulate_routing,
        validate_routing_config,
    )

    def _as_bool_arg(value: Any, default: bool = False) -> bool:
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

    actor = routing_actor_from_teacher_id(args.get("teacher_id"), deps=deps)
    config_path = ensure_teacher_routing_file(actor, deps=deps)
    registry = _registry_for_actor(actor, deps=deps)
    config_override = args.get("config") if isinstance(args.get("config"), dict) else None
    override_validation: Optional[Dict[str, Any]] = None

    if config_override:
        override_validation = validate_routing_config(config_override, registry)
        normalized = override_validation.get("normalized") if isinstance(override_validation.get("normalized"), dict) else {}
        channels = normalized.get("channels") if isinstance(normalized.get("channels"), list) else []
        rules = normalized.get("rules") if isinstance(normalized.get("rules"), list) else []
        channels_by_id: Dict[str, Dict[str, Any]] = {}
        for item in channels:
            if not isinstance(item, dict):
                continue
            channel_id = str(item.get("id") or "").strip()
            if channel_id:
                channels_by_id[channel_id] = item
        compiled = CompiledRouting(
            config=normalized,
            errors=list(override_validation.get("errors") or []),
            warnings=list(override_validation.get("warnings") or []),
            channels_by_id=channels_by_id,
            rules=[r for r in rules if isinstance(r, dict)],
        )
    else:
        compiled = get_compiled_routing(config_path, registry)

    ctx = RoutingContext(
        role=str(args.get("role") or "teacher").strip() or "teacher",
        skill_id=str(args.get("skill_id") or "").strip() or None,
        kind=str(args.get("kind") or "").strip() or None,
        needs_tools=_as_bool_arg(args.get("needs_tools"), False),
        needs_json=_as_bool_arg(args.get("needs_json"), False),
    )
    result = simulate_routing(compiled, ctx)
    result_payload = {"ok": True, "teacher_id": actor, **result}
    if override_validation is not None:
        result_payload["config_override"] = True
        result_payload["override_validation"] = {
            "ok": bool(override_validation.get("ok")),
            "errors": list(override_validation.get("errors") or []),
            "warnings": list(override_validation.get("warnings") or []),
        }
    return result_payload


def teacher_llm_routing_propose(args: Dict[str, Any], *, deps: TeacherLlmRoutingDeps) -> Dict[str, Any]:
    from .llm_routing import create_routing_proposal

    actor = routing_actor_from_teacher_id(args.get("teacher_id"), deps=deps)
    config_path = ensure_teacher_routing_file(actor, deps=deps)
    registry = _registry_for_actor(actor, deps=deps)
    config_payload = args.get("config") if isinstance(args.get("config"), dict) else None
    if not config_payload:
        return {"ok": False, "error": "config_required"}
    note = str(args.get("note") or "").strip()
    result = create_routing_proposal(
        config_path=config_path,
        model_registry=registry,
        config_payload=config_payload,
        actor=actor,
        note=note,
    )
    result["teacher_id"] = actor
    return result


def teacher_llm_routing_apply(args: Dict[str, Any], *, deps: TeacherLlmRoutingDeps) -> Dict[str, Any]:
    from .llm_routing import apply_routing_proposal

    actor = routing_actor_from_teacher_id(args.get("teacher_id"), deps=deps)
    config_path = ensure_teacher_routing_file(actor, deps=deps)
    registry = _registry_for_actor(actor, deps=deps)
    proposal_id = str(args.get("proposal_id") or "").strip()
    approve = bool(args.get("approve", True))
    if not proposal_id:
        return {"ok": False, "error": "proposal_id_required"}
    result = apply_routing_proposal(
        config_path=config_path,
        model_registry=registry,
        proposal_id=proposal_id,
        approve=approve,
        actor=actor,
    )
    result["teacher_id"] = actor
    return result


def teacher_llm_routing_rollback(args: Dict[str, Any], *, deps: TeacherLlmRoutingDeps) -> Dict[str, Any]:
    from .llm_routing import rollback_routing_config

    actor = routing_actor_from_teacher_id(args.get("teacher_id"), deps=deps)
    config_path = ensure_teacher_routing_file(actor, deps=deps)
    registry = _registry_for_actor(actor, deps=deps)
    target_version = args.get("target_version")
    note = str(args.get("note") or "").strip()
    result = rollback_routing_config(
        config_path=config_path,
        model_registry=registry,
        target_version=target_version,
        actor=actor,
        note=note,
    )
    result["teacher_id"] = actor
    return result


def teacher_llm_routing_proposal_get(args: Dict[str, Any], *, deps: TeacherLlmRoutingDeps) -> Dict[str, Any]:
    from .llm_routing import read_proposal

    actor = routing_actor_from_teacher_id(args.get("teacher_id"), deps=deps)
    config_path = ensure_teacher_routing_file(actor, deps=deps)
    proposal_id = str(args.get("proposal_id") or "").strip()
    if not proposal_id:
        return {"ok": False, "error": "proposal_id_required"}
    result = read_proposal(config_path, proposal_id=proposal_id)
    result["teacher_id"] = actor
    result["config_path"] = str(config_path)
    return result
