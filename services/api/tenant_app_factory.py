from __future__ import annotations

import importlib.util
import sys
import types
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from collections import deque
import threading

from fastapi import FastAPI


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
        start = getattr(self.module, "start_tenant_runtime", None)
        if callable(start):
            start()

    def shutdown(self) -> None:
        stop = getattr(self.module, "stop_tenant_runtime", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass
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

    # Reset queues/caches/locks for strict per-tenant isolation.
    _set("UPLOAD_JOB_QUEUE", deque())
    _set("UPLOAD_JOB_LOCK", threading.Lock())
    _set("UPLOAD_JOB_EVENT", threading.Event())
    _set("UPLOAD_JOB_WORKER_STARTED", False)

    _set("EXAM_JOB_QUEUE", deque())
    _set("EXAM_JOB_LOCK", threading.Lock())
    _set("EXAM_JOB_EVENT", threading.Event())
    _set("EXAM_JOB_WORKER_STARTED", False)

    _set("CHAT_JOB_LOCK", threading.Lock())
    _set("CHAT_JOB_EVENT", threading.Event())
    _set("CHAT_JOB_WORKER_STARTED", False)

    _set("CHAT_JOB_LANES", {})
    _set("CHAT_JOB_ACTIVE_LANES", set())
    _set("CHAT_JOB_QUEUED", set())
    _set("CHAT_JOB_TO_LANE", {})
    _set("CHAT_LANE_CURSOR", 0)
    _set("CHAT_WORKER_THREADS", [])
    _set("CHAT_LANE_RECENT", {})

    idempotency_factory = getattr(mod, "create_chat_idempotency_store", None)
    if callable(idempotency_factory):
        _set("CHAT_IDEMPOTENCY_STATE", idempotency_factory(getattr(mod, "CHAT_JOB_DIR")))

    limits = settings.limits
    _set("OCR_MAX_CONCURRENCY", int(limits.ocr))
    _set("LLM_MAX_CONCURRENCY", int(limits.llm_total))
    _set("LLM_MAX_CONCURRENCY_STUDENT", int(limits.llm_student))
    _set("LLM_MAX_CONCURRENCY_TEACHER", int(limits.llm_teacher))
    _set("_OCR_SEMAPHORE", threading.BoundedSemaphore(int(limits.ocr)))
    _set("_LLM_SEMAPHORE", threading.BoundedSemaphore(int(limits.llm_total)))
    _set("_LLM_SEMAPHORE_STUDENT", threading.BoundedSemaphore(int(limits.llm_student)))
    _set("_LLM_SEMAPHORE_TEACHER", threading.BoundedSemaphore(int(limits.llm_teacher)))

    _set("_STUDENT_INFLIGHT", {})
    _set("_STUDENT_INFLIGHT_LOCK", threading.Lock())

    _set("_PROFILE_CACHE", {})
    _set("_PROFILE_CACHE_LOCK", threading.Lock())
    _set("_ASSIGNMENT_DETAIL_CACHE", {})
    _set("_ASSIGNMENT_DETAIL_CACHE_LOCK", threading.Lock())

    _set("_PROFILE_UPDATE_QUEUE", deque())
    _set("_PROFILE_UPDATE_LOCK", threading.Lock())
    _set("_PROFILE_UPDATE_EVENT", threading.Event())
    _set("_PROFILE_UPDATE_WORKER_STARTED", False)

    _set("_TEACHER_SESSION_COMPACT_TS", {})
    _set("_TEACHER_SESSION_COMPACT_LOCK", threading.Lock())
    _set("_SESSION_INDEX_LOCKS", {})
    _set("_SESSION_INDEX_LOCKS_LOCK", threading.Lock())

    _set("DIAG_LOG_PATH", uploads_dir / "diagnostics.log")
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
