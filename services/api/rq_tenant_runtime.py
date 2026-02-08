from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Optional

from .tenant_config_store import TenantConfigStore
from .tenant_registry import TenantRegistry

_TENANT_REGISTRY: Optional[TenantRegistry] = None


def _get_registry() -> TenantRegistry:
    global _TENANT_REGISTRY
    if _TENANT_REGISTRY is None:
        db_path = Path(
            os.getenv(
                "TENANT_DB_PATH",
                str(Path(__file__).resolve().parents[2] / "data" / "_system" / "tenants.sqlite3"),
            )
        )
        store = TenantConfigStore(db_path)
        _TENANT_REGISTRY = TenantRegistry(store)
    return _TENANT_REGISTRY


def load_tenant_module(tenant_id: Optional[str]):
    tid = str(tenant_id or "").strip()
    if not tid:
        return importlib.import_module("services.api.app")
    registry = _get_registry()
    handle = registry.get_or_create(tid)
    return handle.instance.module
