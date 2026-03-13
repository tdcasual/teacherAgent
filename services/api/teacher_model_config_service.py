from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .teacher_provider_registry_service import _catalog

_log = logging.getLogger(__name__)

_LOCKS_GUARD = threading.Lock()
_LOCKS: Dict[str, threading.RLock] = {}
_PURPOSES = ("conversation", "embedding", "ocr", "image_generation")


def _lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        current = _LOCKS.get(key)
        if current is None:
            current = threading.RLock()
            _LOCKS[key] = current
        return current


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _log.debug("JSON parse failed", exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def _default_model_for_mode(
    providers: Dict[str, Any],
    *,
    provider_name: str,
    mode_name: str,
) -> str:
    provider = _as_dict(providers.get(provider_name))
    modes = _as_dict(provider.get("modes"))
    mode = _as_dict(modes.get(mode_name))
    return _as_str(mode.get("default_model"))


def _provider_mode_exists(
    providers: Dict[str, Any],
    *,
    provider_name: str,
    mode_name: str,
) -> bool:
    modes = _as_dict(_as_dict(providers.get(provider_name)).get("modes"))
    return provider_name in providers and mode_name in modes


def _first_provider_mode(
    providers: Dict[str, Any],
    *,
    mode_predicate: Optional[Callable[[str], bool]] = None,
) -> tuple[str, str]:
    for provider_name in sorted(providers.keys()):
        modes = _as_dict(_as_dict(providers.get(provider_name)).get("modes"))
        for mode_name in sorted(modes.keys()):
            if mode_predicate is not None and not mode_predicate(mode_name):
                continue
            return provider_name, mode_name
    return "", ""


def _find_provider_mode(
    registry: Dict[str, Any],
    *,
    provider_hint: str,
    mode_hint: str,
    mode_predicate: Callable[[str], bool],
) -> tuple[str, str, str]:
    providers = _as_dict(registry.get("providers"))
    defaults = _as_dict(registry.get("defaults"))
    if provider_hint and mode_hint and _provider_mode_exists(
        providers,
        provider_name=provider_hint,
        mode_name=mode_hint,
    ):
        return provider_hint, mode_hint, _default_model_for_mode(
            providers,
            provider_name=provider_hint,
            mode_name=mode_hint,
        )

    default_provider = _as_str(defaults.get("provider"))
    default_mode = _as_str(defaults.get("mode"))
    if (
        default_provider
        and default_mode
        and mode_predicate(default_mode)
        and _provider_mode_exists(providers, provider_name=default_provider, mode_name=default_mode)
    ):
        return default_provider, default_mode, _default_model_for_mode(
            providers,
            provider_name=default_provider,
            mode_name=default_mode,
        )

    provider_name, mode_name = _first_provider_mode(providers, mode_predicate=mode_predicate)
    if provider_name and mode_name:
        return provider_name, mode_name, _default_model_for_mode(
            providers,
            provider_name=provider_name,
            mode_name=mode_name,
        )

    provider_name, mode_name = _first_provider_mode(providers)
    if provider_name and mode_name:
        return provider_name, mode_name, _default_model_for_mode(
            providers,
            provider_name=provider_name,
            mode_name=mode_name,
        )

    return "", "", ""


def _default_entry_for_purpose(purpose: str, registry: Dict[str, Any]) -> Dict[str, str]:
    normalized = str(purpose or "").strip().lower()
    if normalized == "embedding":
        provider, mode, model = _find_provider_mode(
            registry,
            provider_hint="",
            mode_hint="",
            mode_predicate=lambda text: ("embed" in text.lower()) or ("vector" in text.lower()),
        )
    elif normalized == "image_generation":
        provider, mode, model = _find_provider_mode(
            registry,
            provider_hint="",
            mode_hint="",
            mode_predicate=lambda text: ("image" in text.lower()) or ("vision" in text.lower()),
        )
    elif normalized == "ocr":
        provider, mode, model = _find_provider_mode(
            registry,
            provider_hint="",
            mode_hint="",
            mode_predicate=lambda text: "ocr" in text.lower(),
        )
        if not provider:
            provider, mode, model = _find_provider_mode(
                registry,
                provider_hint="",
                mode_hint="",
                mode_predicate=lambda text: "chat" in text.lower(),
            )
    else:
        provider, mode, model = _find_provider_mode(
            registry,
            provider_hint="",
            mode_hint="",
            mode_predicate=lambda text: "chat" in text.lower(),
        )
    return {
        "provider": provider,
        "mode": mode,
        "model": model,
    }


def _normalize_entry(
    *,
    purpose: str,
    raw: Dict[str, Any],
    registry: Dict[str, Any],
) -> Dict[str, str]:
    default_entry = _default_entry_for_purpose(purpose, registry)
    provider = _as_str(raw.get("provider")) or default_entry.get("provider", "")
    mode = _as_str(raw.get("mode")) or default_entry.get("mode", "")
    model = _as_str(raw.get("model")) or default_entry.get("model", "")

    providers = _as_dict(registry.get("providers"))
    provider_cfg = _as_dict(providers.get(provider))
    modes = _as_dict(provider_cfg.get("modes"))
    mode_cfg = _as_dict(modes.get(mode))

    if not provider_cfg or not mode_cfg:
        return default_entry
    if not model:
        model = _as_str(mode_cfg.get("default_model"))
    return {"provider": provider, "mode": mode, "model": model}


def _default_payload(actor: str, now_iso: str, registry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": now_iso,
        "updated_by": actor,
        "models": {
            purpose: _default_entry_for_purpose(purpose, registry)
            for purpose in _PURPOSES
        },
    }


@dataclass(frozen=True)
class TeacherModelConfigDeps:
    resolve_teacher_id: Callable[[Optional[str]], str]
    teacher_workspace_dir: Callable[[str], Path]
    atomic_write_json: Callable[[Path, Dict[str, Any]], None]
    now_iso: Callable[[], str]
    resolve_model_registry: Callable[[str], Dict[str, Any]]


def teacher_model_config_path(actor: str, *, deps: TeacherModelConfigDeps) -> Path:
    return deps.teacher_workspace_dir(actor) / "model_config.json"


def resolve_teacher_model_config(
    teacher_id: Optional[str],
    *,
    deps: TeacherModelConfigDeps,
) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(teacher_id)
    registry = deps.resolve_model_registry(actor)
    path = teacher_model_config_path(actor, deps=deps)
    with _lock(path):
        payload = _read_json(path)
        if not payload:
            payload = _default_payload(actor, deps.now_iso(), registry)
            deps.atomic_write_json(path, payload)
            return payload

        models = _as_dict(payload.get("models"))
        normalized_models = {
            purpose: _normalize_entry(
                purpose=purpose,
                raw=_as_dict(models.get(purpose)),
                registry=registry,
            )
            for purpose in _PURPOSES
        }
        payload["schema_version"] = 1
        payload["updated_at"] = _as_str(payload.get("updated_at")) or deps.now_iso()
        payload["updated_by"] = _as_str(payload.get("updated_by")) or actor
        payload["models"] = normalized_models
        deps.atomic_write_json(path, payload)
        return payload


def teacher_model_config_get(args: Dict[str, Any], *, deps: TeacherModelConfigDeps) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(args.get("teacher_id"))
    registry = deps.resolve_model_registry(actor)
    config = resolve_teacher_model_config(actor, deps=deps)
    return {
        "ok": True,
        "teacher_id": actor,
        "config": config,
        "catalog": _catalog(registry),
        "config_path": str(teacher_model_config_path(actor, deps=deps)),
    }


def teacher_model_config_update(args: Dict[str, Any], *, deps: TeacherModelConfigDeps) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(args.get("teacher_id"))
    registry = deps.resolve_model_registry(actor)
    current = resolve_teacher_model_config(actor, deps=deps)
    incoming = _as_dict(args.get("models"))

    next_models = dict(_as_dict(current.get("models")))
    for purpose in _PURPOSES:
        if purpose not in incoming:
            continue
        next_models[purpose] = _normalize_entry(
            purpose=purpose,
            raw=_as_dict(incoming.get(purpose)),
            registry=registry,
        )

    next_payload = {
        "schema_version": 1,
        "updated_at": deps.now_iso(),
        "updated_by": actor,
        "models": {
            purpose: _normalize_entry(
                purpose=purpose,
                raw=_as_dict(next_models.get(purpose)),
                registry=registry,
            )
            for purpose in _PURPOSES
        },
    }
    path = teacher_model_config_path(actor, deps=deps)
    with _lock(path):
        deps.atomic_write_json(path, next_payload)

    return {
        "ok": True,
        "teacher_id": actor,
        "config": next_payload,
        "catalog": _catalog(registry),
        "config_path": str(path),
    }


__all__ = [
    "TeacherModelConfigDeps",
    "teacher_model_config_get",
    "teacher_model_config_update",
    "resolve_teacher_model_config",
    "teacher_model_config_path",
]
