from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .app_routes import register_routes
from .runtime.lifecycle import app_lifespan

_CORE_PATH = Path(__file__).resolve().with_name("app_core.py")


def _load_core():
    module_suffix = str(__name__).split(".")[-1]
    module_name = f"services.api._core_{module_suffix}"
    if os.getenv("PYTEST_CURRENT_TEST"):
        sys.modules.pop(module_name, None)
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, _CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load app_core")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


_core = _load_core()
_APP_CORE = _core

app = FastAPI(title="Physics Agent API", version="0.2.0", lifespan=app_lifespan)

origins = os.getenv("CORS_ORIGINS", "*")
origins_list = [o.strip() for o in origins.split(",")] if origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app, _core)

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
            pass
        if name in self.__dict__:
            try:
                del self.__dict__[name]
            except Exception:
                pass
        return None


sys.modules[__name__].__class__ = _AppModule
