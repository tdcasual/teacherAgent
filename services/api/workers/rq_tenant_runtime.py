from __future__ import annotations

import importlib
import os
import threading
from pathlib import Path
from typing import Any, Optional

from services.api.tenant_config_store import TenantConfigStore
from services.api.tenant_registry import TenantRegistry

_TENANT_REGISTRY: Optional[TenantRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def _get_registry() -> TenantRegistry:
    global _TENANT_REGISTRY
    if _TENANT_REGISTRY is not None:
        return _TENANT_REGISTRY
    with _REGISTRY_LOCK:
        if _TENANT_REGISTRY is not None:
            return _TENANT_REGISTRY
        db_path = Path(
            os.getenv(
                "TENANT_DB_PATH",
                str(Path(__file__).resolve().parents[3] / "data" / "_system" / "tenants.sqlite3"),
            )
        )
        store = TenantConfigStore(db_path)
        _TENANT_REGISTRY = TenantRegistry(store)
    return _TENANT_REGISTRY


def load_tenant_module(tenant_id: Optional[str]) -> Any:
    tid = str(tenant_id or "").strip()
    if not tid:
        return importlib.import_module("services.api.app")
    registry = _get_registry()
    handle = registry.get_or_create(tid)
    return handle.instance.module
