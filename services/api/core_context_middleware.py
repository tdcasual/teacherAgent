from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from .auth_service import (
    AuthError,
    get_current_principal,
    reset_current_principal,
    resolve_principal_from_headers,
    set_current_principal,
)
from .observability import OBSERVABILITY
from .request_context import REQUEST_ID, new_request_id
from .wiring import CURRENT_CORE


def _is_chart_asset_path(path: str) -> bool:
    value = str(path or "").strip()
    return value.startswith("/charts/") or value.startswith("/chart-runs/")


def _resolve_chart_query_principal(request: Request) -> Any:
    path = str(request.url.path)
    if not _is_chart_asset_path(path):
        return None
    token = str(request.query_params.get("access_token") or "").strip()
    if not token:
        return None
    synthetic_headers = {"authorization": f"Bearer {token}"}
    return resolve_principal_from_headers(
        synthetic_headers,
        path=path,
        method=request.method,
        allow_exempt=True,
    )


def build_set_core_context_middleware(
    *,
    default_core: Any,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def _set_core_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get("x-request-id") or new_request_id()
        start = time.perf_counter()
        rid_token = REQUEST_ID.set(rid)
        state = getattr(request.app, "state", None)
        core_from_state = getattr(state, "core", None) if state is not None else None
        container = getattr(state, "container", None) if state is not None else None
        core_from_container = getattr(container, "core", None) if container is not None else None
        active_core = core_from_container or core_from_state or default_core
        core_token = CURRENT_CORE.set(active_core)
        principal_token = None
        status_code = 500
        route_template = str(request.url.path)
        OBSERVABILITY.inc_inflight()
        try:
            principal = get_current_principal()
            if principal is None:
                try:
                    principal = resolve_principal_from_headers(
                        request.headers,
                        path=str(request.url.path),
                        method=request.method,
                        allow_exempt=True,
                    )
                except AuthError as exc:
                    if exc.detail != "missing_authorization":
                        raise
                    principal = _resolve_chart_query_principal(request)
                    if principal is None:
                        raise
                if principal is not None:
                    principal_token = set_current_principal(principal)
            response = await call_next(request)
            status_code = int(getattr(response, "status_code", 200) or 200)
            route = request.scope.get("route")
            route_path = getattr(route, "path", None)
            if isinstance(route_path, str) and route_path:
                route_template = route_path
            response.headers["x-request-id"] = rid
            return response
        except AuthError as exc:
            status_code = int(exc.status_code)
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        except Exception:
            status_code = 500
            logging.getLogger(__name__).exception("Unhandled error in request middleware")
            return JSONResponse(status_code=500, content={"detail": "internal_error"})
        finally:
            elapsed = time.perf_counter() - start
            OBSERVABILITY.record(
                method=request.method,
                route=route_template,
                status_code=status_code,
                latency_sec=elapsed,
            )
            OBSERVABILITY.dec_inflight()
            if principal_token is not None:
                reset_current_principal(principal_token)
            CURRENT_CORE.reset(core_token)
            REQUEST_ID.reset(rid_token)

    return _set_core_context
