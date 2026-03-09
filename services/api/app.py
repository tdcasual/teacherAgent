from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .analysis_metrics_service import AnalysisMetricsService
from .app_routes import register_routes
from .auth_service import require_principal
from .container import build_app_container
from .core_context_middleware import build_set_core_context_middleware
from .core_runtime import build_core_runtime
from .observability import OBSERVABILITY
from .rate_limit import rate_limit_middleware
from .request_context import RequestIdFilter
from .runtime.lifecycle import app_lifespan
from .runtime_settings import AppSettings, load_settings
from .wiring import CURRENT_CORE, set_default_core

_log = logging.getLogger(__name__)


def _cors_origins() -> tuple[list[str], bool]:
    origins = os.getenv("CORS_ORIGINS", "*")
    origins_list = [o.strip() for o in origins.split(",")] if origins else ["*"]
    allow_credentials = "*" not in origins_list
    if not allow_credentials:
        _log.warning(
            "CORS_ORIGINS is '*'; credentials disabled. Set specific origins for production."
        )
    return origins_list, allow_credentials


def _attach_request_id_filter_once() -> None:
    root = logging.getLogger()
    if any(isinstance(existing, RequestIdFilter) for existing in root.filters):
        return
    root.addFilter(RequestIdFilter())


def _ops_metrics_payload(core: Any) -> dict[str, Any]:
    metrics = dict(OBSERVABILITY.snapshot())
    analysis_metrics = getattr(core, 'analysis_metrics_service', None)
    analysis_snapshot = getattr(analysis_metrics, 'snapshot', None)
    if callable(analysis_snapshot):
        metrics['analysis_runtime'] = analysis_snapshot()
    else:
        metrics['analysis_runtime'] = AnalysisMetricsService().snapshot()
    return metrics


def _register_ops_routes(app_obj: FastAPI) -> None:
    @app_obj.get("/ops/metrics")
    async def ops_metrics():
        require_principal(roles=("service", "admin"))
        return {"ok": True, "metrics": _ops_metrics_payload(app_obj.state.core)}

    @app_obj.get("/ops/slo")
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


def create_app(settings: AppSettings) -> FastAPI:
    core = build_core_runtime(settings=settings)
    if getattr(core, 'analysis_metrics_service', None) is None:
        setattr(core, 'analysis_metrics_service', AnalysisMetricsService())
    set_default_core(core)
    app_obj = FastAPI(title="Physics Agent API", version="0.2.0", lifespan=app_lifespan)
    app_obj.state.settings = settings
    app_obj.state.core = core
    app_obj.state.container = build_app_container(core=core)

    origins_list, allow_credentials = _cors_origins()
    app_obj.add_middleware(
        CORSMiddleware,
        allow_origins=origins_list,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app_obj.middleware("http")(rate_limit_middleware)
    app_obj.middleware("http")(build_set_core_context_middleware(default_core=core))
    register_routes(app_obj, core)
    _register_ops_routes(app_obj)
    _attach_request_id_filter_once()

    CURRENT_CORE.set(core)
    return app_obj


def get_core(app_obj: FastAPI | None = None) -> Any:
    target = app_obj if app_obj is not None else app
    for candidate in (target, getattr(target, "default_app", None)):
        state = getattr(candidate, "state", None) if candidate is not None else None
        core = getattr(state, "core", None) if state is not None else None
        if core is not None:
            return core
    raise RuntimeError("app.state.core missing")


def _build_runtime_entrypoint() -> Any:
    default_app = create_app(load_settings())
    if __name__ != "services.api.app":
        return default_app

    app_root = Path(get_core(default_app).APP_ROOT or Path(__file__).resolve().parents[2])
    tenant_admin_key = str(os.getenv("TENANT_ADMIN_KEY", "") or "").strip()
    tenant_db_path = Path(
        os.getenv(
            "TENANT_DB_PATH",
            str(app_root / "data" / "_system" / "tenants.sqlite3"),
        )
    )

    try:
        from .tenant_admin_api import TenantAdminDeps, create_admin_app
        from .tenant_config_store import TenantConfigStore
        from .tenant_dispatcher import MultiTenantDispatcher
        from .tenant_registry import TenantRegistry

        tenant_store = TenantConfigStore(tenant_db_path)
        tenant_registry = TenantRegistry(tenant_store)
        admin_app = create_admin_app(
            deps=TenantAdminDeps(
                admin_key=tenant_admin_key,
                store=tenant_store,
                registry=tenant_registry,
            )
        )
        return MultiTenantDispatcher(
            default_app=default_app,
            admin_app=admin_app,
            registry=tenant_registry,
        )
    except Exception:
        _log.error(
            "Multi-tenant initialization failed; falling back to single-tenant mode",
            exc_info=True,
        )
        return default_app


app = _build_runtime_entrypoint()
