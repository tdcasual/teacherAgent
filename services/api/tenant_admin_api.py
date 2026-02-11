from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .tenant_config_store import TenantConfig, TenantConfigStore
from .tenant_registry import TenantRegistry, validate_tenant_id


def _validate_tenant_path(raw: str, label: str) -> str:
    """Resolve and validate that a tenant path is within the allowed base, if configured."""
    resolved = Path(raw).expanduser().resolve()
    allowed_base = os.getenv("TENANT_DATA_BASE_DIR", "").strip()
    if allowed_base:
        base = Path(allowed_base).resolve()
        if not str(resolved).startswith(str(base) + os.sep) and resolved != base:
            raise HTTPException(status_code=400, detail=f"{label} must be under {base}")
    return str(resolved)


class TenantUpsertRequest(BaseModel):
    data_dir: str = Field(min_length=1)
    uploads_dir: str = Field(min_length=1)
    enabled: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class TenantAdminDeps:
    admin_key: str
    store: TenantConfigStore
    registry: TenantRegistry


def _require_admin(deps: TenantAdminDeps, x_admin_key: Optional[str]) -> None:
    expected = (deps.admin_key or "").strip()
    if not expected:
        raise HTTPException(status_code=401, detail="admin key not configured")
    got = str(x_admin_key or "")
    if not hmac.compare_digest(got, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def create_admin_app(*, deps: TenantAdminDeps) -> FastAPI:
    app = FastAPI(title="Tenant Admin", version="0.1.0")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/admin/tenants")
    async def list_tenants(x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")):
        _require_admin(deps, x_admin_key)
        tenants = deps.store.list(enabled_only=False)
        return {
            "ok": True,
            "tenants": [
                {
                    "tenant_id": t.tenant_id,
                    "data_dir": t.data_dir,
                    "uploads_dir": t.uploads_dir,
                    "enabled": bool(t.enabled),
                    "updated_at": t.updated_at,
                }
                for t in tenants
            ],
        }

    @app.put("/admin/tenants/{tenant_id}")
    async def upsert_tenant(
        tenant_id: str,
        req: TenantUpsertRequest,
        x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    ):
        _require_admin(deps, x_admin_key)
        try:
            tid = validate_tenant_id(tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid tenant_id")

        cfg = deps.store.upsert(
            TenantConfig(
                tenant_id=tid,
                data_dir=_validate_tenant_path(req.data_dir, "data_dir"),
                uploads_dir=_validate_tenant_path(req.uploads_dir, "uploads_dir"),
                enabled=bool(req.enabled),
                extra=dict(req.extra or {}),
            )
        )
        # Make it live immediately.
        if cfg.enabled:
            deps.registry.replace(tid)
        else:
            deps.registry.unload(tid)
        return {"ok": True, "tenant_id": tid}

    @app.delete("/admin/tenants/{tenant_id}")
    async def delete_tenant(
        tenant_id: str,
        x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    ):
        _require_admin(deps, x_admin_key)
        try:
            tid = validate_tenant_id(tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid tenant_id")
        deps.store.disable(tid)
        deps.registry.unload(tid)
        return {"ok": True, "tenant_id": tid}

    return app

