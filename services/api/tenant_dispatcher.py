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


def _normalize_scope_path(scope: Dict[str, Any]) -> str:
    path = scope.get("path") or ""
    if isinstance(path, bytes):
        return path.decode("utf-8", errors="ignore")
    return str(path)


class MultiTenantDispatcher:
    def __init__(self, *, default_app: ASGIApp, admin_app: ASGIApp, registry: TenantRegistry):
        self.default_app = default_app
        self.admin_app = admin_app
        self.registry = registry

    async def __call__(self, scope, receive, send):  # type: ignore[override]
        scope_type = scope.get("type")
        if scope_type != "http":
            return await self.default_app(scope, receive, send)
        path = _normalize_scope_path(scope)

        if path.startswith("/admin/"):
            return await self.admin_app(scope, receive, send)

        split = _split_tenant_path(str(path))
        if split is None:
            return await self.default_app(scope, receive, send)

        tenant_id, rest_path = split
        handle = await self._resolve_tenant_handle(scope=scope, send=send, tenant_id=tenant_id)
        if handle is None:
            return
        new_scope = dict(scope)
        new_scope["path"] = rest_path
        return await self._dispatch_tenant_app(handle=handle, scope=new_scope, receive=receive, send=send)

    async def _resolve_tenant_handle(
        self,
        *,
        scope: Dict[str, Any],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        tenant_id: str,
    ) -> Optional[Any]:
        try:
            principal = resolve_principal_from_scope(scope, allow_exempt=False)
        except AuthError as exc:
            await self._send_simple(
                send,
                status=exc.status_code,
                body=exc.detail.encode("utf-8", errors="ignore"),
            )
            return None
        if not principal_can_access_tenant(principal, tenant_id):
            await self._send_simple(send, status=403, body=b"forbidden_tenant_scope")
            return None
        try:
            handle = self.registry.get_or_create(tenant_id)
        except Exception:
            _log.warning("failed to resolve tenant %s", tenant_id, exc_info=True)
            await self._send_simple(send, status=404, body=b"tenant not found")
            return None
        try:
            handle.instance.activate()
        except Exception:
            _log.warning("failed to activate tenant %s", tenant_id, exc_info=True)
            await self._send_simple(send, status=500, body=b"tenant activation failed")
            return None
        return handle

    async def _dispatch_tenant_app(
        self,
        *,
        handle: Any,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        # Explicitly set CURRENT_CORE so tenant-aware code sees the right runtime core.
        state = getattr(getattr(handle, "app", None), "state", None)
        core = getattr(state, "core", None) if state is not None else None
        if core is None:
            core = getattr(handle.instance.module, "_APP_CORE", None)
        token = CURRENT_CORE.set(core) if core is not None else None
        try:
            await handle.app(scope, receive, send)
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
