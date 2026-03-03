from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .app_routes import register_routes
from .auth_service import require_principal
from .core_context_middleware import build_set_core_context_middleware
from .observability import OBSERVABILITY
from .rate_limit import rate_limit_middleware
from .request_context import RequestIdFilter
from .runtime.lifecycle import app_lifespan

_log = logging.getLogger(__name__)

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


def get_core() -> Any:
    default_app = globals().get("_DEFAULT_APP")
    app_obj = globals().get("app")
    for candidate in (default_app, app_obj):
        state = getattr(candidate, "state", None)
        core = getattr(state, "core", None) if state is not None else None
        if core is not None:
            return core
    return _APP_CORE

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
app.middleware("http")(build_set_core_context_middleware(default_core=_core))

register_routes(app, _core)

# Attach request-id filter so all loggers include it
logging.getLogger().addFilter(RequestIdFilter())


@app.get("/ops/metrics")
async def ops_metrics():
    require_principal(roles=("service", "admin"))
    return {"ok": True, "metrics": OBSERVABILITY.snapshot()}


@app.get("/ops/slo")
async def ops_slo():
    require_principal(roles=("service", "admin"))
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
