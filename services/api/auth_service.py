from __future__ import annotations

import base64
import contextvars
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Set

_log = logging.getLogger(__name__)


_CURRENT_PRINCIPAL: contextvars.ContextVar[Optional["AuthPrincipal"]] = contextvars.ContextVar(
    "CURRENT_PRINCIPAL",
    default=None,
)


@dataclass(frozen=True)
class AuthPrincipal:
    actor_id: str
    role: str
    tenant_id: str = ""
    exp: Optional[int] = None
    claims: Dict[str, Any] = field(default_factory=dict)


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "auth_error")


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def auth_required() -> bool:
    raw = os.getenv("AUTH_REQUIRED")
    if raw is None:
        # Auto-detect: require auth only when secret is configured (or in test mode, skip)
        if bool(os.getenv("PYTEST_CURRENT_TEST")):
            return False
        # If AUTH_TOKEN_SECRET is not set, auth cannot work — disable it for dev mode
        return bool(_secret())
    return _truthy(raw)


def _auth_exempt_path(path: str) -> bool:
    value = str(path or "").strip() or "/"
    if value == "/health":
        return True
    if value in {
        "/auth/student/identify",
        "/auth/student/login",
        "/auth/student/set-password",
        "/auth/teacher/identify",
        "/auth/teacher/login",
        "/auth/teacher/set-password",
        "/auth/admin/login",
    }:
        return True
    if value.startswith("/admin/"):
        return True
    return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    raw = str(text or "")
    if not raw:
        return b""
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _secret() -> str:
    return str(os.getenv("AUTH_TOKEN_SECRET", "") or "").strip()


def _is_production(getenv: Callable[[str, Optional[str]], Optional[str]] = os.getenv) -> bool:
    env = str(getenv("APP_ENV", None) or getenv("ENV", None) or "development").strip().lower()
    return env in {"prod", "production"}


def validate_auth_secret_policy(*, getenv: Callable[[str, Optional[str]], Optional[str]] = os.getenv) -> None:
    if not _truthy(getenv("AUTH_REQUIRED", None)):
        return
    if str(getenv("AUTH_TOKEN_SECRET", None) or "").strip():
        return
    if _is_production(getenv):
        raise RuntimeError("AUTH_TOKEN_SECRET is required when AUTH_REQUIRED is enabled in production")


def _normalize_role(value: Any) -> str:
    return str(value or "").strip().lower()


def access_token_ttl_sec() -> int:
    raw = str(os.getenv("AUTH_ACCESS_TOKEN_TTL_SEC", "28800") or "28800").strip()
    try:
        value = int(raw)
    except Exception:
        value = 28800
    return max(300, value)


def mint_test_token(claims: Dict[str, Any], *, secret: str) -> str:
    payload_json = json.dumps(claims or {}, ensure_ascii=False, separators=(",", ":"))
    payload_segment = _b64url_encode(payload_json.encode("utf-8"))
    digest = hmac.new(secret.encode("utf-8"), payload_segment.encode("ascii"), hashlib.sha256).digest()
    sig_segment = _b64url_encode(digest)
    return f"{payload_segment}.{sig_segment}"


def _decode_bearer_token(token: str, *, secret: str) -> AuthPrincipal:
    text = str(token or "").strip()
    if not text:
        raise AuthError(401, "missing_bearer_token")

    parts = text.split(".")
    if len(parts) != 2:
        raise AuthError(401, "invalid_token_format")

    payload_segment, sig_segment = parts
    expected = hmac.new(secret.encode("utf-8"), payload_segment.encode("ascii"), hashlib.sha256).digest()
    try:
        got = _b64url_decode(sig_segment)
    except Exception:
        raise AuthError(401, "invalid_token_signature")
    if not hmac.compare_digest(got, expected):
        raise AuthError(401, "invalid_token_signature")

    try:
        payload_raw = _b64url_decode(payload_segment)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        raise AuthError(401, "invalid_token_payload")
    if not isinstance(payload, dict):
        raise AuthError(401, "invalid_token_payload")

    actor_id = str(payload.get("sub") or payload.get("actor_id") or "").strip()
    role = _normalize_role(payload.get("role"))
    if not actor_id or role not in {"teacher", "student", "admin", "service"}:
        raise AuthError(401, "invalid_token_claims")

    exp_raw = payload.get("exp")
    exp: Optional[int] = None
    if exp_raw is not None:
        try:
            exp = int(exp_raw)
        except Exception:
            raise AuthError(401, "invalid_token_exp")
        if exp <= int(time.time()):
            raise AuthError(401, "token_expired")

    tenant_id = str(payload.get("tenant_id") or payload.get("tid") or "").strip()
    return AuthPrincipal(actor_id=actor_id, role=role, tenant_id=tenant_id, exp=exp, claims=dict(payload))


def mint_access_token(
    *,
    subject_id: str,
    role: str,
    tenant_id: str = "",
    token_version: Optional[int] = None,
) -> str:
    sid = str(subject_id or "").strip()
    role_norm = _normalize_role(role)
    if not sid or role_norm not in {"teacher", "student", "admin", "service"}:
        raise AuthError(400, "invalid_token_claims")
    secret = _secret()
    if not secret:
        raise AuthError(500, "auth_token_secret_missing")
    now = int(time.time())
    claims: Dict[str, Any] = {
        "sub": sid,
        "role": role_norm,
        "iat": now,
        "exp": now + access_token_ttl_sec(),
    }
    tid = str(tenant_id or "").strip()
    if tid:
        claims["tenant_id"] = tid
    if token_version is not None:
        claims["tv"] = int(token_version)
    return mint_test_token(claims, secret=secret)


def resolve_principal_from_headers(
    headers: Mapping[str, Any],
    *,
    path: str = "",
    method: str = "",
    allow_exempt: bool = True,
) -> Optional[AuthPrincipal]:
    if not auth_required():
        return None

    if allow_exempt:
        if str(method or "").strip().upper() == "OPTIONS":
            return None
        if _auth_exempt_path(path):
            return None

    secret = _secret()
    if not secret:
        raise AuthError(500, "auth_token_secret_missing")

    authz = str(headers.get("authorization") or headers.get("Authorization") or "").strip()
    if not authz:
        raise AuthError(401, "missing_authorization")
    if not authz.lower().startswith("bearer "):
        raise AuthError(401, "invalid_authorization_scheme")
    token = authz[7:].strip()
    principal = _decode_bearer_token(token, secret=secret)

    claims = principal.claims if isinstance(principal.claims, dict) else {}
    if principal.role in {"teacher", "student"} and claims.get("tv") is not None:
        raw_token_version = claims.get("tv")
        try:
            token_version = int(str(raw_token_version))
        except Exception:
            raise AuthError(401, "invalid_token_claims")
        try:
            from .auth_registry_service import validate_subject_token_version

            if not validate_subject_token_version(
                role=principal.role,
                subject_id=principal.actor_id,
                token_version=token_version,
            ):
                raise AuthError(401, "token_revoked")
        except AuthError:
            raise
        except Exception:
            _log.warning("auth token version validation failed", exc_info=True)
            raise AuthError(401, "invalid_token_claims")
    return principal


def resolve_principal_from_scope(scope: Dict[str, Any], *, allow_exempt: bool = True) -> Optional[AuthPrincipal]:
    headers_map: Dict[str, str] = {}
    for item in scope.get("headers") or []:
        try:
            key_raw, value_raw = item
        except Exception:
            _log.debug("operation failed", exc_info=True)
            continue
        key = key_raw.decode("latin-1", errors="ignore") if isinstance(key_raw, (bytes, bytearray)) else str(key_raw)
        value = value_raw.decode("latin-1", errors="ignore") if isinstance(value_raw, (bytes, bytearray)) else str(value_raw)
        headers_map[key] = value
    path = scope.get("path") or ""
    if isinstance(path, bytes):
        path = path.decode("utf-8", errors="ignore")
    method = scope.get("method") or ""
    return resolve_principal_from_headers(headers_map, path=str(path), method=str(method), allow_exempt=allow_exempt)


def set_current_principal(principal: Optional[AuthPrincipal]) -> contextvars.Token:
    return _CURRENT_PRINCIPAL.set(principal)


def reset_current_principal(token: Any) -> None:
    _CURRENT_PRINCIPAL.reset(token)


def get_current_principal() -> Optional[AuthPrincipal]:
    return _CURRENT_PRINCIPAL.get()


def require_principal(*, roles: Optional[Sequence[str]] = None) -> Optional[AuthPrincipal]:
    principal = get_current_principal()
    if not auth_required():
        return principal
    if principal is None:
        raise AuthError(401, "missing_authorization")
    if roles:
        allowed: Set[str] = {str(role or "").strip().lower() for role in roles}
        if principal.role not in allowed:
            raise AuthError(403, "forbidden")
    return principal


def principal_can_access_tenant(principal: Optional[AuthPrincipal], tenant_id: str) -> bool:
    if not auth_required():
        return True
    if principal is None:
        return False
    if principal.role == "admin":
        return True
    claimed = str(principal.tenant_id or "").strip()
    if not claimed:
        return False
    return claimed == str(tenant_id or "").strip()


def resolve_teacher_scope(teacher_id: Optional[str], *, required_for_admin: bool = False) -> Optional[str]:
    raw = str(teacher_id or "").strip() or None
    if not auth_required():
        return raw

    principal = require_principal(roles=("teacher", "admin"))
    if principal is None:
        return raw

    if principal.role == "teacher":
        if raw and raw != principal.actor_id:
            raise AuthError(403, "forbidden_teacher_scope")
        return principal.actor_id

    target = raw or principal.actor_id
    if required_for_admin and not target:
        raise AuthError(400, "teacher_id_required")
    return target or None


def resolve_student_scope(student_id: Optional[str], *, required_for_admin: bool = False) -> Optional[str]:
    raw = str(student_id or "").strip() or None
    if not auth_required():
        return raw

    principal = require_principal(roles=("student", "admin"))
    if principal is None:
        return raw

    if principal.role == "student":
        if raw and raw != principal.actor_id:
            raise AuthError(403, "forbidden_student_scope")
        return principal.actor_id

    target = raw or principal.actor_id
    if required_for_admin and not target:
        raise AuthError(400, "student_id_required")
    return target or None


def enforce_chat_job_access(job: Mapping[str, Any]) -> None:
    if not auth_required():
        return

    principal = require_principal(roles=("teacher", "student", "admin"))
    if principal is None or principal.role == "admin":
        return

    payload = dict(job or {})
    role = _normalize_role(payload.get("role"))
    req_payload = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    if not isinstance(req_payload, dict):
        req_payload = {}

    teacher_owner = str(payload.get("teacher_id") or req_payload.get("teacher_id") or "").strip()
    student_owner = str(payload.get("student_id") or req_payload.get("student_id") or "").strip()

    if principal.role == "teacher":
        if role and role != "teacher":
            raise AuthError(403, "forbidden_chat_job")
        if not teacher_owner or teacher_owner != principal.actor_id:
            raise AuthError(403, "forbidden_chat_job")
        return

    if principal.role == "student":
        if role and role != "student":
            raise AuthError(403, "forbidden_chat_job")
        if not student_owner or student_owner != principal.actor_id:
            raise AuthError(403, "forbidden_chat_job")
        return


def enforce_upload_job_access(
    job: Mapping[str, Any],
    *,
    owner_field: str = "teacher_id",
    detail: str = "forbidden_upload_job",
) -> None:
    if not auth_required():
        return

    principal = require_principal(roles=("teacher", "admin"))
    if principal is None or principal.role == "admin":
        return

    payload = dict(job or {})
    owner = str(payload.get(owner_field) or "").strip()
    if not owner or owner != principal.actor_id:
        raise AuthError(403, detail)


def bind_chat_request_to_principal(req: Any) -> Any:
    principal = require_principal(roles=("teacher", "student", "admin"))
    if principal is None:
        return req

    if principal.role == "teacher":
        req.role = "teacher"
        req.teacher_id = principal.actor_id
        req.student_id = None
        return req

    if principal.role == "student":
        req.role = "student"
        req.student_id = principal.actor_id
        req.teacher_id = None
        return req

    role = _normalize_role(getattr(req, "role", None))
    if role not in {"teacher", "student"}:
        raise AuthError(400, "admin_role_required")
    if role == "teacher":
        teacher_id = str(getattr(req, "teacher_id", "") or "").strip()
        if not teacher_id:
            raise AuthError(400, "teacher_id_required_for_admin")
        req.student_id = None
        return req

    student_id = str(getattr(req, "student_id", "") or "").strip()
    if not student_id:
        raise AuthError(400, "student_id_required_for_admin")
    req.teacher_id = None
    return req


__all__ = [
    "AuthPrincipal",
    "AuthError",
    "auth_required",
    "resolve_principal_from_headers",
    "resolve_principal_from_scope",
    "set_current_principal",
    "reset_current_principal",
    "get_current_principal",
    "require_principal",
    "principal_can_access_tenant",
    "resolve_teacher_scope",
    "resolve_student_scope",
    "enforce_chat_job_access",
    "enforce_upload_job_access",
    "bind_chat_request_to_principal",
    "mint_test_token",
    "mint_access_token",
    "access_token_ttl_sec",
]
