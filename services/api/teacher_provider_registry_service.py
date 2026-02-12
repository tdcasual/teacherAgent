from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import requests  # type: ignore[import-untyped]

_PROVIDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
_LOCKS_GUARD = threading.Lock()
_LOCKS: Dict[str, threading.RLock] = {}


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


def _is_prod(getenv: Callable[[str, Optional[str]], Optional[str]]) -> bool:
    env = _as_str(getenv("APP_ENV", None) or getenv("ENV", None) or "development").lower()
    return env in {"prod", "production"}


def _master_key(getenv: Callable[[str, Optional[str]], Optional[str]]) -> str:
    key = _as_str(getenv("MASTER_KEY", None))
    if key:
        return key
    if _is_prod(getenv):
        raise RuntimeError("MASTER_KEY is required in production")
    return _as_str(getenv("MASTER_KEY_DEV_DEFAULT", "dev-master-key-unsafe-change-me"))


def validate_master_key_policy(*, getenv: Callable[[str, Optional[str]], Optional[str]]) -> Dict[str, Any]:
    key = _as_str(getenv("MASTER_KEY", None))
    if _is_prod(getenv) and not key:
        raise RuntimeError("MASTER_KEY is required in production")
    return {"ok": True, "is_production": _is_prod(getenv), "has_master_key": bool(key)}


def _derive_key(master: str) -> bytes:
    return hashlib.sha256(master.encode("utf-8")).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(out[:length])


def encrypt_secret(secret: str, master: str) -> str:
    plain = _as_str(secret).encode("utf-8")
    if not plain:
        return ""
    key = _derive_key(master)
    nonce = secrets.token_bytes(12)
    stream = _keystream(key, nonce, len(plain))
    cipher = bytes(a ^ b for a, b in zip(plain, stream))
    tag = hmac.new(key, b"tprv-v1:" + nonce + cipher, hashlib.sha256).digest()[:16]
    raw = b"\x01" + nonce + tag + cipher
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decrypt_secret(secret: str, master: str) -> str:
    text = _as_str(secret)
    if not text:
        return ""
    pad = "=" * (-len(text) % 4)
    raw = base64.urlsafe_b64decode(text + pad)
    if len(raw) < 29 or raw[0] != 1:
        raise ValueError("invalid_encrypted_secret")
    nonce = raw[1:13]
    expected = raw[13:29]
    cipher = raw[29:]
    key = _derive_key(master)
    actual = hmac.new(key, b"tprv-v1:" + nonce + cipher, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(expected, actual):
        raise ValueError("secret_integrity_check_failed")
    plain = bytes(a ^ b for a, b in zip(cipher, _keystream(key, nonce, len(cipher))))
    return plain.decode("utf-8")


def _mask(secret: str) -> str:
    text = _as_str(secret)
    if not text:
        return ""
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}****{text[-4:]}"


def _normalize_provider_id(value: Any) -> str:
    text = _as_str(value)
    if text and _PROVIDER_ID_RE.match(text):
        return text
    return ""


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", _as_str(value)).strip("_")
    return text or "provider"


def _new_provider_id(display_name: str) -> str:
    return f"tprv_{_slug(display_name).lower()[:40]}_{uuid.uuid4().hex[:6]}"


def _normalize_base_url(value: Any, *, allow_http: bool) -> str:
    text = _as_str(value)
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
        return ""
    if parsed.scheme == "http" and not allow_http:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}".rstrip("/")


def _is_private_host(hostname: str) -> bool:
    host = _as_str(hostname).strip("[]").strip().lower()
    if not host:
        return True
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        addr = ipaddress.ip_address(host)
        return bool(addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast)
    except Exception:
        return False


def _is_base_url_safe_for_probe(base_url: str) -> bool:
    text = _as_str(base_url)
    parsed = urlparse(text)
    host = _as_str(parsed.hostname)
    if not host:
        return False
    if _is_private_host(host):
        return False
    return True


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _providers(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = payload.get("providers")
    if not isinstance(raw, list):
        return []
    return [dict(x) for x in raw if isinstance(x, dict)]


def _catalog(registry: Dict[str, Any]) -> Dict[str, Any]:
    providers_raw = _as_dict(registry.get("providers"))
    providers: List[Dict[str, Any]] = []
    for provider_name in sorted(providers_raw.keys()):
        provider_cfg = _as_dict(providers_raw.get(provider_name))
        # Ignore malformed provider entries so bad data does not pollute catalog output.
        if not provider_cfg:
            continue
        modes_raw = _as_dict(provider_cfg.get("modes"))
        modes = []
        for mode_name in sorted(modes_raw.keys()):
            mode_cfg = _as_dict(modes_raw.get(mode_name))
            modes.append(
                {
                    "mode": mode_name,
                    "default_model": _as_str(mode_cfg.get("default_model")),
                    "model_env": _as_str(mode_cfg.get("model_env")),
                }
            )
        providers.append(
            {
                "provider": provider_name,
                "source": "private" if _as_bool(provider_cfg.get("private_provider"), False) else "shared",
                "base_url": _as_str(provider_cfg.get("base_url")),
                "modes": modes,
            }
        )
    defaults = _as_dict(registry.get("defaults"))
    routing_cfg = _as_dict(registry.get("routing"))
    return {
        "providers": providers,
        "defaults": {
            "provider": _as_str(defaults.get("provider")),
            "mode": _as_str(defaults.get("mode")),
        },
        "fallback_chain": [str(x) for x in (routing_cfg.get("fallback_chain") or []) if _as_str(x)],
    }


@dataclass(frozen=True)
class TeacherProviderRegistryDeps:
    model_registry: Dict[str, Any]
    resolve_teacher_id: Callable[[Optional[str]], str]
    teacher_workspace_dir: Callable[[str], Path]
    atomic_write_json: Callable[[Path, Dict[str, Any]], None]
    now_iso: Callable[[], str]
    getenv: Callable[[str, Optional[str]], Optional[str]]


def teacher_provider_registry_path(actor: str, *, deps: TeacherProviderRegistryDeps) -> Path:
    return deps.teacher_workspace_dir(actor) / "provider_registry.json"


def teacher_provider_registry_audit_path(actor: str, *, deps: TeacherProviderRegistryDeps) -> Path:
    return deps.teacher_workspace_dir(actor) / "provider_registry_audit.jsonl"


def _default_payload(actor: str, now_iso: str) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": now_iso,
        "updated_by": actor,
        "providers": [],
    }


def ensure_teacher_provider_registry(actor: str, *, deps: TeacherProviderRegistryDeps) -> Path:
    path = teacher_provider_registry_path(actor, deps=deps)
    with _lock(path):
        payload = _read_json(path)
        if not payload:
            deps.atomic_write_json(path, _default_payload(actor, deps.now_iso()))
            return path
        payload.setdefault("schema_version", 1)
        payload.setdefault("updated_at", deps.now_iso())
        payload.setdefault("updated_by", actor)
        payload.setdefault("providers", [])
        deps.atomic_write_json(path, payload)
    return path


def _load_private(actor: str, *, deps: TeacherProviderRegistryDeps) -> List[Dict[str, Any]]:
    payload = _read_json(ensure_teacher_provider_registry(actor, deps=deps))
    return _providers(payload)


def _save_private(actor: str, providers: List[Dict[str, Any]], *, deps: TeacherProviderRegistryDeps) -> None:
    payload = _default_payload(actor, deps.now_iso())
    payload["providers"] = providers
    deps.atomic_write_json(ensure_teacher_provider_registry(actor, deps=deps), payload)


def _public_provider(item: Dict[str, Any]) -> Dict[str, Any]:
    provider_id = _normalize_provider_id(item.get("id"))
    return {
        "id": provider_id,
        "provider": provider_id,
        "display_name": _as_str(item.get("display_name")) or provider_id,
        "base_url": _as_str(item.get("base_url")),
        "api_key_masked": _as_str(item.get("api_key_masked")),
        "default_mode": "openai-chat",
        "default_model": _as_str(item.get("default_model")),
        "enabled": _as_bool(item.get("enabled"), True),
        "created_at": _as_str(item.get("created_at")),
        "updated_at": _as_str(item.get("updated_at")),
        "source": "private",
    }


def _append_audit(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(payload, ensure_ascii=False) + "\n")


def merged_model_registry_for_actor(actor: str, *, deps: TeacherProviderRegistryDeps) -> Dict[str, Any]:
    merged = copy.deepcopy(deps.model_registry if isinstance(deps.model_registry, dict) else {})
    providers = merged.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        merged["providers"] = providers
    for item in _load_private(actor, deps=deps):
        provider_id = _normalize_provider_id(item.get("id"))
        if not provider_id or not _as_bool(item.get("enabled"), True):
            continue
        base_url = _as_str(item.get("base_url"))
        if not base_url:
            continue
        providers[provider_id] = {
            "private_provider": True,
            "display_name": _as_str(item.get("display_name")) or provider_id,
            "base_url": base_url,
            "auth": {"type": "bearer"},
            "api_key_envs": [],
            "modes": {
                "openai-chat": {
                    "endpoint": "/chat/completions",
                    "model_env": "",
                    "default_model": _as_str(item.get("default_model")),
                }
            },
        }
    return merged


def merged_model_registry(teacher_id: Optional[str], *, deps: TeacherProviderRegistryDeps) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(teacher_id)
    return merged_model_registry_for_actor(actor, deps=deps)


def teacher_provider_registry_get(args: Dict[str, Any], *, deps: TeacherProviderRegistryDeps) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(args.get("teacher_id"))
    path = ensure_teacher_provider_registry(actor, deps=deps)
    merged = merged_model_registry_for_actor(actor, deps=deps)
    return {
        "ok": True,
        "teacher_id": actor,
        "providers": [_public_provider(x) for x in _load_private(actor, deps=deps)],
        "shared_catalog": _catalog(deps.model_registry if isinstance(deps.model_registry, dict) else {}),
        "catalog": _catalog(merged),
        "config_path": str(path),
    }


def teacher_provider_registry_create(args: Dict[str, Any], *, deps: TeacherProviderRegistryDeps) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(args.get("teacher_id"))
    allow_http = not _is_prod(deps.getenv)
    provider_id = _normalize_provider_id(args.get("provider_id") or args.get("id")) or _new_provider_id(_as_str(args.get("display_name")))
    base_url = _normalize_base_url(args.get("base_url"), allow_http=allow_http)
    api_key = _as_str(args.get("api_key"))
    default_model = _as_str(args.get("default_model"))
    display_name = _as_str(args.get("display_name")) or provider_id
    enabled = _as_bool(args.get("enabled"), True)

    if not provider_id:
        return {"ok": False, "error": "invalid_provider_id"}
    if not base_url:
        return {"ok": False, "error": "invalid_base_url"}
    if not api_key:
        return {"ok": False, "error": "api_key_required"}
    # Allow overriding shared providers — private entry takes precedence in merged registry

    path = ensure_teacher_provider_registry(actor, deps=deps)
    with _lock(path):
        providers = _load_private(actor, deps=deps)
        if any(_normalize_provider_id(x.get("id")) == provider_id for x in providers):
            return {"ok": False, "error": "provider_id_exists"}
        key = _master_key(deps.getenv)
        record = {
            "id": provider_id,
            "display_name": display_name,
            "base_url": base_url,
            "api_key_encrypted": encrypt_secret(api_key, key),
            "api_key_masked": _mask(api_key),
            "default_model": default_model,
            "enabled": enabled,
            "created_at": deps.now_iso(),
            "created_by": actor,
            "updated_at": deps.now_iso(),
            "updated_by": actor,
        }
        providers.append(record)
        _save_private(actor, providers, deps=deps)
        _append_audit(
            teacher_provider_registry_audit_path(actor, deps=deps),
            {"ts": deps.now_iso(), "actor": actor, "action": "create", "provider_id": provider_id, "enabled": enabled},
        )
    return {"ok": True, "teacher_id": actor, "provider": _public_provider(record)}


def teacher_provider_registry_update(args: Dict[str, Any], *, deps: TeacherProviderRegistryDeps) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(args.get("teacher_id"))
    provider_id = _normalize_provider_id(args.get("provider_id") or args.get("id"))
    if not provider_id:
        return {"ok": False, "error": "provider_id_required"}
    path = ensure_teacher_provider_registry(actor, deps=deps)
    allow_http = not _is_prod(deps.getenv)
    with _lock(path):
        providers = _load_private(actor, deps=deps)
        idx = next((i for i, item in enumerate(providers) if _normalize_provider_id(item.get("id")) == provider_id), -1)
        if idx < 0:
            return {"ok": False, "error": "provider_not_found"}
        current = dict(providers[idx])
        if "display_name" in args:
            current["display_name"] = _as_str(args.get("display_name")) or provider_id
        if "base_url" in args:
            raw_base_url = _as_str(args.get("base_url"))
            if raw_base_url:
                base_url = _normalize_base_url(raw_base_url, allow_http=allow_http)
                if not base_url:
                    return {"ok": False, "error": "invalid_base_url"}
            else:
                base_url = ""
            current["base_url"] = base_url
        if "default_model" in args:
            current["default_model"] = _as_str(args.get("default_model"))
        if "enabled" in args:
            current["enabled"] = _as_bool(args.get("enabled"), True)
        api_key = _as_str(args.get("api_key"))
        if api_key:
            key = _master_key(deps.getenv)
            current["api_key_encrypted"] = encrypt_secret(api_key, key)
            current["api_key_masked"] = _mask(api_key)
        current["updated_at"] = deps.now_iso()
        current["updated_by"] = actor
        providers[idx] = current
        _save_private(actor, providers, deps=deps)
        _append_audit(
            teacher_provider_registry_audit_path(actor, deps=deps),
            {"ts": deps.now_iso(), "actor": actor, "action": "update", "provider_id": provider_id, "rotated_key": bool(api_key)},
        )
    return {"ok": True, "teacher_id": actor, "provider": _public_provider(current)}


def teacher_provider_registry_delete(args: Dict[str, Any], *, deps: TeacherProviderRegistryDeps) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(args.get("teacher_id"))
    provider_id = _normalize_provider_id(args.get("provider_id") or args.get("id"))
    if not provider_id:
        return {"ok": False, "error": "provider_id_required"}
    path = ensure_teacher_provider_registry(actor, deps=deps)
    with _lock(path):
        providers = _load_private(actor, deps=deps)
        idx = next((i for i, item in enumerate(providers) if _normalize_provider_id(item.get("id")) == provider_id), -1)
        if idx < 0:
            return {"ok": False, "error": "provider_not_found"}
        current = dict(providers[idx])
        current["enabled"] = False
        current["updated_at"] = deps.now_iso()
        current["updated_by"] = actor
        current["deleted_at"] = deps.now_iso()
        providers[idx] = current
        _save_private(actor, providers, deps=deps)
        _append_audit(
            teacher_provider_registry_audit_path(actor, deps=deps),
            {"ts": deps.now_iso(), "actor": actor, "action": "disable", "provider_id": provider_id},
        )
    return {"ok": True, "teacher_id": actor, "provider_id": provider_id}


def _find_private(actor: str, provider_id: str, *, deps: TeacherProviderRegistryDeps) -> Optional[Dict[str, Any]]:
    normalized = _normalize_provider_id(provider_id)
    if not normalized:
        return None
    for item in _load_private(actor, deps=deps):
        if _normalize_provider_id(item.get("id")) == normalized:
            return dict(item)
    return None


def resolve_private_provider_target(
    *,
    actor: str,
    provider_id: str,
    mode: str,
    model: str,
    deps: TeacherProviderRegistryDeps,
) -> Optional[Dict[str, Any]]:
    provider = _find_private(actor, provider_id, deps=deps)
    if not provider or not _as_bool(provider.get("enabled"), True):
        return None
    mode_val = _as_str(mode) or "openai-chat"
    if mode_val != "openai-chat":
        return None
    key = _master_key(deps.getenv)
    encrypted = _as_str(provider.get("api_key_encrypted"))
    if not encrypted:
        return None
    api_key = decrypt_secret(encrypted, key)
    model_val = _as_str(model) or _as_str(provider.get("default_model"))
    if not model_val:
        return None
    defaults = _as_dict(deps.model_registry.get("defaults"))
    return {
        "provider": provider_id,
        "mode": mode_val,
        "model": model_val,
        "base_url": _as_str(provider.get("base_url")),
        "endpoint": "/chat/completions",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        "timeout_sec": defaults.get("timeout_sec"),
        "retry": defaults.get("retry"),
    }


def resolve_provider_target(
    teacher_id: Optional[str],
    provider_id: str,
    mode: str,
    model: str,
    *,
    deps: TeacherProviderRegistryDeps,
) -> Optional[Dict[str, Any]]:
    actor = deps.resolve_teacher_id(teacher_id)
    return resolve_private_provider_target(actor=actor, provider_id=provider_id, mode=mode, model=model, deps=deps)


def resolve_shared_provider_target(
    *,
    provider_id: str,
    mode: str = "openai-chat",
    deps: TeacherProviderRegistryDeps,
) -> Optional[Dict[str, Any]]:
    """Resolve base_url + headers for a shared (built-in) provider so we can probe its /models endpoint."""
    providers_raw = _as_dict(deps.model_registry.get("providers"))
    prov_cfg = _as_dict(providers_raw.get(provider_id))
    if not prov_cfg:
        return None
    if _as_bool(prov_cfg.get("private_provider"), False):
        return None
    mode_val = _as_str(mode) or "openai-chat"
    modes = _as_dict(prov_cfg.get("modes"))
    mode_cfg = _as_dict(modes.get(mode_val))

    # Resolve base_url: mode env → provider env → mode static → provider static
    base_url = _as_str(deps.getenv(mode_cfg.get("base_url_env", ""), None)) or _as_str(deps.getenv(prov_cfg.get("base_url_env", ""), None))
    if not base_url:
        base_url = _as_str(mode_cfg.get("base_url")) or _as_str(prov_cfg.get("base_url"))
    if not base_url:
        return None

    # Resolve api_key: LLM_API_KEY → provider api_key_envs
    api_key = _as_str(deps.getenv("LLM_API_KEY", None))
    if not api_key:
        for env_name in (prov_cfg.get("api_key_envs") or []):
            val = _as_str(deps.getenv(env_name, None))
            if val:
                api_key = val
                break
    if not api_key:
        return None

    # Build headers based on auth type
    auth = _as_dict(prov_cfg.get("auth"))
    auth_type = _as_str(auth.get("type")) or "bearer"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if auth_type == "bearer":
        header = _as_str(auth.get("header")) or "Authorization"
        prefix = auth.get("prefix", "Bearer ")
        headers[header] = f"{prefix}{api_key}"
    elif auth_type == "x-goog-api-key":
        headers["x-goog-api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    endpoint = _as_str(mode_cfg.get("endpoint")) or "/chat/completions"
    return {
        "provider": provider_id,
        "mode": mode_val,
        "base_url": base_url.rstrip("/"),
        "endpoint": endpoint,
        "headers": headers,
    }


def teacher_provider_registry_probe_models(args: Dict[str, Any], *, deps: TeacherProviderRegistryDeps) -> Dict[str, Any]:
    actor = deps.resolve_teacher_id(args.get("teacher_id"))
    provider_id = _normalize_provider_id(args.get("provider_id") or args.get("id"))
    if not provider_id:
        return {"ok": False, "error": "provider_id_required"}
    # 1. Try private provider first
    provider = _find_private(actor, provider_id, deps=deps)
    if provider:
        target = resolve_private_provider_target(
            actor=actor,
            provider_id=provider_id,
            mode="openai-chat",
            model=_as_str(provider.get("default_model")) or "gpt-4.1-mini",
            deps=deps,
        )
    else:
        # 2. Fallback to shared provider
        target = resolve_shared_provider_target(provider_id=provider_id, deps=deps)
    if not target:
        return {"ok": False, "error": "provider_not_found"}
    base_url = _as_str(target.get("base_url"))
    if not _is_base_url_safe_for_probe(base_url):
        return {"ok": False, "error": "unsafe_probe_target"}
    try:
        resp = requests.get(
            f"{base_url.rstrip('/')}/models",
            headers=target.get("headers") if isinstance(target.get("headers"), dict) else {},
            timeout=10,
            allow_redirects=False,
        )
        if resp.status_code >= 400:
            return {"ok": False, "error": "probe_failed", "status_code": resp.status_code, "detail": (resp.text or "")[:400]}
        payload = resp.json() if resp.text else {}
        data_items = payload.get("data") if isinstance(payload, dict) else None
        models_raw = data_items if isinstance(data_items, list) else []
        models = []
        for item in models_raw:
            if isinstance(item, dict):
                model_id = _as_str(item.get("id"))
                if model_id:
                    models.append(model_id)
        return {"ok": True, "teacher_id": actor, "provider_id": provider_id, "models": sorted(set(models))}
    except Exception as exc:
        return {"ok": False, "error": "probe_exception", "detail": str(exc)[:400]}


__all__ = [
    "TeacherProviderRegistryDeps",
    "validate_master_key_policy",
    "teacher_provider_registry_get",
    "teacher_provider_registry_create",
    "teacher_provider_registry_update",
    "teacher_provider_registry_delete",
    "teacher_provider_registry_probe_models",
    "merged_model_registry",
    "merged_model_registry_for_actor",
    "resolve_provider_target",
    "resolve_private_provider_target",
    "resolve_shared_provider_target",
    "_catalog",
]
