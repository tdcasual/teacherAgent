from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from services.api.runtime import bootstrap
from services.api.runtime_settings import load_settings
from services.api.wiring import CURRENT_CORE

from .app import create_app

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TenantLimits:
    llm_total: int = 30
    llm_student: int = 2
    llm_teacher: int = 10
    ocr: int = 5


@dataclass(frozen=True)
class TenantSettings:
    tenant_id: str
    data_dir: Path
    uploads_dir: Path
    limits: TenantLimits = TenantLimits()


class TenantModuleProxy:
    """Module-like view backed by a tenant app core."""

    def __init__(self, app: Any) -> None:
        self.app = app
        state = getattr(app, "state", None)
        core = getattr(state, "core", None) if state is not None else None
        if core is None:
            raise RuntimeError("tenant app missing app.state.core")
        self._APP_CORE = core

    def get_core(self) -> Any:
        return self._APP_CORE

    def activate(self) -> None:
        # Instance-scoped app/core already carries tenant settings.
        return

    def __getattr__(self, name: str) -> Any:
        return getattr(self._APP_CORE, name)


@dataclass
class TenantAppInstance:
    tenant_id: str
    module_name: str
    module: Any
    app: Any
    settings: Optional[TenantSettings] = None

    def activate(self) -> None:
        activate = getattr(self.module, "activate", None)
        if callable(activate):
            activate()

    def startup(self) -> None:
        self.activate()
        core = getattr(self.module, "get_core", lambda: None)()
        token = CURRENT_CORE.set(core) if core is not None else None
        try:
            bootstrap.start_runtime(app_mod=self.app)
        finally:
            if token is not None:
                CURRENT_CORE.reset(token)

    def shutdown(self) -> None:
        self.activate()
        core = getattr(self.module, "get_core", lambda: None)()
        token = CURRENT_CORE.set(core) if core is not None else None
        try:
            try:
                bootstrap.stop_runtime(app_mod=self.app)
            except Exception:
                _log.warning("shutdown failed for tenant module %s", self.module_name, exc_info=True)
        finally:
            if token is not None:
                CURRENT_CORE.reset(token)


def _tenant_env(settings: TenantSettings) -> dict[str, str]:
    env = dict(os.environ)
    data_dir = settings.data_dir.expanduser().resolve()
    uploads_dir = settings.uploads_dir.expanduser().resolve()
    limits = settings.limits

    env["TENANT_ID"] = str(settings.tenant_id)
    env["DATA_DIR"] = str(data_dir)
    env["UPLOADS_DIR"] = str(uploads_dir)
    env["DIAG_LOG_PATH"] = str(uploads_dir / "diagnostics.log")
    env["OCR_MAX_CONCURRENCY"] = str(int(limits.ocr))
    env["LLM_MAX_CONCURRENCY"] = str(int(limits.llm_total))
    env["LLM_MAX_CONCURRENCY_STUDENT"] = str(int(limits.llm_student))
    env["LLM_MAX_CONCURRENCY_TEACHER"] = str(int(limits.llm_teacher))
    return env


def create_tenant_app(settings: TenantSettings) -> TenantAppInstance:
    app_settings = load_settings(env=_tenant_env(settings))
    tenant_app = create_app(app_settings)
    module = TenantModuleProxy(tenant_app)
    return TenantAppInstance(
        tenant_id=settings.tenant_id,
        module_name=f"tenant:{settings.tenant_id}",
        module=module,
        app=tenant_app,
        settings=settings,
    )
