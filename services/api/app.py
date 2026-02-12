from __future__ import annotations

import importlib.util
import logging
import os
import sys
import time
import types
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .app_routes import register_routes
from .auth_service import (
    AuthError,
    get_current_principal,
    reset_current_principal,
    resolve_principal_from_headers,
    set_current_principal,
)
from .request_context import REQUEST_ID, RequestIdFilter, new_request_id
from .rate_limit import rate_limit_middleware
from .runtime.lifecycle import app_lifespan
from .wiring import CURRENT_CORE
from .observability import OBSERVABILITY

_CORE_PATH = Path(__file__).resolve().with_name("app_core.py")


def _core_env_fingerprint() -> tuple[str, ...]:
    keys = (
        "DATA_DIR",
        "UPLOADS_DIR",
        "TENANT_ID",
        "TENANT_DATA_DIR",
        "TENANT_UPLOADS_DIR",
    )
    return tuple(str(os.getenv(key, "")) for key in keys)


def _load_core():
    module_suffix = str(__name__).split(".")[-1]
    module_name = f"services.api._core_{module_suffix}"
    is_main_app = module_suffix == "app"
    canonical_name = "services.api.app_core"
    fp = _core_env_fingerprint()
    existing = sys.modules.get(module_name)
    should_reload = bool(os.getenv("PYTEST_CURRENT_TEST"))
    if existing is not None and getattr(existing, "_CORE_ENV_FINGERPRINT", None) != fp:
        should_reload = True
    if should_reload:
        sys.modules.pop(module_name, None)
        if is_main_app:
            sys.modules.pop(canonical_name, None)
        existing = None
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, _CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load app_core")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    if is_main_app:
        sys.modules[canonical_name] = module
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    setattr(module, "_CORE_ENV_FINGERPRINT", fp)
    return module


_core = _load_core()
_APP_CORE = _core

app = FastAPI(title="Physics Agent API", version="0.2.0", lifespan=app_lifespan)
app.state.core = _core

origins = os.getenv("CORS_ORIGINS", "*")
origins_list = [o.strip() for o in origins.split(",")] if origins else ["*"]
_allow_credentials = "*" not in origins_list
if not _allow_credentials:
    logging.getLogger(__name__).warning(
        "CORS_ORIGINS is '*'; credentials disabled. Set specific origins for production."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(rate_limit_middleware)

register_routes(app, _core)

# Attach request-id filter so all loggers include it
logging.getLogger().addFilter(RequestIdFilter())


@app.middleware("http")
async def _set_core_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    rid = request.headers.get("x-request-id") or new_request_id()
    start = time.perf_counter()
    rid_token = REQUEST_ID.set(rid)
    state = getattr(request.app, "state", None)
    core_from_state = getattr(state, "core", None) if state is not None else None
    container = getattr(state, "container", None) if state is not None else None
    core_from_container = getattr(container, "core", None) if container is not None else None
    active_core = core_from_container or core_from_state or _core
    core_token = CURRENT_CORE.set(active_core)
    principal_token = None
    status_code = 500
    route_template = str(request.url.path)
    OBSERVABILITY.inc_inflight()
    try:
        principal = get_current_principal()
        if principal is None:
            principal = resolve_principal_from_headers(
                request.headers,
                path=str(request.url.path),
                method=request.method,
                allow_exempt=True,
            )
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


@app.get("/ops/metrics")
async def ops_metrics():
    return {"ok": True, "metrics": OBSERVABILITY.snapshot()}


@app.get("/ops/slo")
async def ops_slo():
    snap = OBSERVABILITY.snapshot()
    return {
        "ok": True,
        "slo": snap.get("slo") or {},
        "uptime_sec": snap.get("uptime_sec", 0.0),
        "inflight_requests": snap.get("inflight_requests", 0),
        "http_requests_total": snap.get("http_requests_total", 0),
        "http_error_rate": snap.get("http_error_rate", 0.0),
        "http_latency_p95_sec": ((snap.get("http_latency_sec") or {}).get("p95") or 0.0),
    }

if __name__ == "services.api.app":
    _DEFAULT_APP = app

    TENANT_ADMIN_KEY = str(os.getenv("TENANT_ADMIN_KEY", "") or "").strip()
    TENANT_DB_PATH = Path(
        os.getenv(
            "TENANT_DB_PATH",
            str(_core.APP_ROOT / "data" / "_system" / "tenants.sqlite3"),
        )
    )

    try:
        from .tenant_admin_api import TenantAdminDeps, create_admin_app
        from .tenant_config_store import TenantConfigStore
        from .tenant_dispatcher import MultiTenantDispatcher
        from .tenant_registry import TenantRegistry

        _TENANT_STORE = TenantConfigStore(TENANT_DB_PATH)
        _TENANT_REGISTRY = TenantRegistry(_TENANT_STORE)
        _ADMIN_APP = create_admin_app(
            deps=TenantAdminDeps(
                admin_key=TENANT_ADMIN_KEY,
                store=_TENANT_STORE,
                registry=_TENANT_REGISTRY,
            )
        )

        app = MultiTenantDispatcher(default_app=_DEFAULT_APP, admin_app=_ADMIN_APP, registry=_TENANT_REGISTRY)
    except Exception:
        logging.getLogger(__name__).error(
            "Multi-tenant initialization failed; falling back to single-tenant mode",
            exc_info=True,
        )
        app = _DEFAULT_APP


class _AppModule(types.ModuleType):
    def __getattr__(self, name: str) -> Any:
        return getattr(_core, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("__") or name in {"app", "_DEFAULT_APP", "_APP_CORE"}:
            return super().__setattr__(name, value)
        try:
            setattr(_core, name, value)
        except Exception:
            logging.getLogger(__name__).debug("setattr(%s) on _core failed", name, exc_info=True)
        if name in self.__dict__:
            try:
                del self.__dict__[name]
            except Exception:
                pass
        return None


sys.modules[__name__].__class__ = _AppModule
