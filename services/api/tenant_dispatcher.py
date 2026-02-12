from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from .auth_service import AuthError, principal_can_access_tenant, resolve_principal_from_scope

from .tenant_registry import TenantRegistry
from .wiring import CURRENT_CORE


_log = logging.getLogger(__name__)
_TENANT_PATH_RE = re.compile(r"^/t/([A-Za-z0-9][A-Za-z0-9_-]{0,63})(/.*)?$")

ASGIApp = Callable[[Dict[str, Any], Callable[[], Awaitable[Dict[str, Any]]], Callable[[Dict[str, Any]], Awaitable[None]]], Awaitable[None]]


def _split_tenant_path(path: str) -> Optional[Tuple[str, str]]:
    match = _TENANT_PATH_RE.match(path or "")
    if not match:
        return None
    tenant_id = match.group(1) or ""
    rest = match.group(2) or ""
    rest_path = rest if rest else "/"
    return tenant_id, rest_path


class MultiTenantDispatcher:
    def __init__(self, *, default_app: ASGIApp, admin_app: ASGIApp, registry: TenantRegistry):
        self.default_app = default_app
        self.admin_app = admin_app
        self.registry = registry

    async def __call__(self, scope, receive, send):  # type: ignore[override]
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            return await self.default_app(scope, receive, send)
        if scope_type != "http":
            return await self.default_app(scope, receive, send)

        path = scope.get("path") or ""
        if isinstance(path, bytes):
            path = path.decode("utf-8", errors="ignore")

        if path.startswith("/admin/"):
            return await self.admin_app(scope, receive, send)

        split = _split_tenant_path(str(path))
        if split is None:
            return await self.default_app(scope, receive, send)

        tenant_id, rest_path = split
        try:
            principal = resolve_principal_from_scope(scope, allow_exempt=False)
        except AuthError as exc:
            return await self._send_simple(send, status=exc.status_code, body=exc.detail.encode("utf-8", errors="ignore"))
        if not principal_can_access_tenant(principal, tenant_id):
            return await self._send_simple(send, status=403, body=b"forbidden_tenant_scope")
        try:
            handle = self.registry.get_or_create(tenant_id)
        except Exception:
            _log.warning("failed to resolve tenant %s", tenant_id, exc_info=True)
            return await self._send_simple(send, status=404, body=b"tenant not found")

        new_scope = dict(scope)
        new_scope["path"] = rest_path
        # Explicitly set CURRENT_CORE so tenant-aware code sees the right module
        core = getattr(handle.instance.module, '_APP_CORE', None)
        token = CURRENT_CORE.set(core) if core is not None else None
        try:
            return await handle.app(new_scope, receive, send)
        finally:
            if token is not None:
                CURRENT_CORE.reset(token)

    async def _send_simple(
        self, send: Callable[[Dict[str, Any]], Awaitable[None]], *, status: int, body: bytes
    ) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": int(status),
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": body or b""})
