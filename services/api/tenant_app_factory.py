from __future__ import annotations

import importlib.util
import logging
import sys
import types
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI

from services.api.runtime import bootstrap
from services.api.runtime.runtime_state import reset_runtime_state
from services.api.wiring import CURRENT_CORE

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

@dataclass
class TenantAppInstance:
    tenant_id: str
    module_name: str
    module: types.ModuleType
    app: Any

    def startup(self) -> None:
        core = getattr(self.module, '_APP_CORE', None)
        token = CURRENT_CORE.set(core) if core is not None else None
        try:
            bootstrap.start_runtime(app_mod=self.module)
        finally:
            if token is not None:
                CURRENT_CORE.reset(token)

    def shutdown(self) -> None:
        core = getattr(self.module, '_APP_CORE', None)
        token = CURRENT_CORE.set(core) if core is not None else None
        try:
            try:
                bootstrap.stop_runtime(app_mod=self.module)
            except Exception:
                _log.warning("shutdown failed for tenant module %s", self.module_name, exc_info=True)
        finally:
            if token is not None:
                CURRENT_CORE.reset(token)
            sys.modules.pop(self.module_name, None)

_APP_PY_PATH = Path(__file__).resolve().with_name("app.py")


def _configure_module_for_tenant(mod: types.ModuleType, settings: TenantSettings) -> None:
    data_dir = settings.data_dir.expanduser().resolve()
    uploads_dir = settings.uploads_dir.expanduser().resolve()

    targets = [mod]
    core = getattr(mod, "_APP_CORE", None)
    if core is not None and core is not mod:
        targets.append(core)

    def _set(name: str, value: Any) -> None:
        for target in targets:
            setattr(target, name, value)

    _set("TENANT_ID", settings.tenant_id)
    _set("DATA_DIR", data_dir)
    _set("UPLOADS_DIR", uploads_dir)
    _set("LLM_ROUTING_PATH", data_dir / "llm_routing.json")

    _set("STUDENT_SESSIONS_DIR", data_dir / "student_chat_sessions")
    _set("TEACHER_WORKSPACES_DIR", data_dir / "teacher_workspaces")
    _set("TEACHER_SESSIONS_DIR", data_dir / "teacher_chat_sessions")
    _set("STUDENT_SUBMISSIONS_DIR", data_dir / "student_submissions")

    _set("UPLOAD_JOB_DIR", uploads_dir / "assignment_jobs")
    _set("EXAM_UPLOAD_JOB_DIR", uploads_dir / "exam_jobs")
    _set("CHAT_JOB_DIR", uploads_dir / "chat_jobs")

    limits = settings.limits
    _set("OCR_MAX_CONCURRENCY", int(limits.ocr))
    _set("LLM_MAX_CONCURRENCY", int(limits.llm_total))
    _set("LLM_MAX_CONCURRENCY_STUDENT", int(limits.llm_student))
    _set("LLM_MAX_CONCURRENCY_TEACHER", int(limits.llm_teacher))

    _set("DIAG_LOG_PATH", uploads_dir / "diagnostics.log")

    for target in targets:
        idempotency_factory = getattr(target, "create_chat_idempotency_store", None)
        if callable(idempotency_factory):
            reset_runtime_state(target, create_chat_idempotency_store=idempotency_factory)
        _set("_DIAG_LOGGER", None)

def create_tenant_app(settings: TenantSettings) -> TenantAppInstance:
    module_suffix = uuid.uuid4().hex[:10]
    module_name = f"services.api._tenant_{settings.tenant_id}_{module_suffix}"
    spec = importlib.util.spec_from_file_location(module_name, _APP_PY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load tenant module spec")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[arg-type]

    _configure_module_for_tenant(module, settings)
    tenant_app = getattr(module, "app", None)
    if tenant_app is None:
        raise RuntimeError("tenant module missing app")
    return TenantAppInstance(
        tenant_id=settings.tenant_id,
        module_name=module_name,
        module=module,
        app=tenant_app,
    )
