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

    setattr(mod, "DATA_DIR", data_dir)
    setattr(mod, "UPLOADS_DIR", uploads_dir)
    setattr(mod, "LLM_ROUTING_PATH", data_dir / "llm_routing.json")

    setattr(mod, "STUDENT_SESSIONS_DIR", data_dir / "student_chat_sessions")
    setattr(mod, "TEACHER_WORKSPACES_DIR", data_dir / "teacher_workspaces")
    setattr(mod, "TEACHER_SESSIONS_DIR", data_dir / "teacher_chat_sessions")
    setattr(mod, "STUDENT_SUBMISSIONS_DIR", data_dir / "student_submissions")

    setattr(mod, "UPLOAD_JOB_DIR", uploads_dir / "assignment_jobs")
    setattr(mod, "EXAM_UPLOAD_JOB_DIR", uploads_dir / "exam_jobs")
    setattr(mod, "CHAT_JOB_DIR", uploads_dir / "chat_jobs")

    # Reset queues/caches/locks for strict per-tenant isolation.
    setattr(mod, "UPLOAD_JOB_QUEUE", deque())
    setattr(mod, "UPLOAD_JOB_LOCK", threading.Lock())
    setattr(mod, "UPLOAD_JOB_EVENT", threading.Event())
    setattr(mod, "UPLOAD_JOB_WORKER_STARTED", False)

    setattr(mod, "EXAM_JOB_QUEUE", deque())
    setattr(mod, "EXAM_JOB_LOCK", threading.Lock())
    setattr(mod, "EXAM_JOB_EVENT", threading.Event())
    setattr(mod, "EXAM_JOB_WORKER_STARTED", False)

    setattr(mod, "CHAT_JOB_LOCK", threading.Lock())
    setattr(mod, "CHAT_JOB_EVENT", threading.Event())
    setattr(mod, "CHAT_JOB_WORKER_STARTED", False)

    setattr(mod, "CHAT_JOB_LANES", {})
    setattr(mod, "CHAT_JOB_ACTIVE_LANES", set())
    setattr(mod, "CHAT_JOB_QUEUED", set())
    setattr(mod, "CHAT_JOB_TO_LANE", {})
    setattr(mod, "CHAT_LANE_CURSOR", 0)
    setattr(mod, "CHAT_WORKER_THREADS", [])
    setattr(mod, "CHAT_LANE_RECENT", {})

    idempotency_factory = getattr(mod, "create_chat_idempotency_store", None)
    if callable(idempotency_factory):
        setattr(mod, "CHAT_IDEMPOTENCY_STATE", idempotency_factory(getattr(mod, "CHAT_JOB_DIR")))

    limits = settings.limits
    setattr(mod, "OCR_MAX_CONCURRENCY", int(limits.ocr))
    setattr(mod, "LLM_MAX_CONCURRENCY", int(limits.llm_total))
    setattr(mod, "LLM_MAX_CONCURRENCY_STUDENT", int(limits.llm_student))
    setattr(mod, "LLM_MAX_CONCURRENCY_TEACHER", int(limits.llm_teacher))
    setattr(mod, "_OCR_SEMAPHORE", threading.BoundedSemaphore(int(limits.ocr)))
    setattr(mod, "_LLM_SEMAPHORE", threading.BoundedSemaphore(int(limits.llm_total)))
    setattr(mod, "_LLM_SEMAPHORE_STUDENT", threading.BoundedSemaphore(int(limits.llm_student)))
    setattr(mod, "_LLM_SEMAPHORE_TEACHER", threading.BoundedSemaphore(int(limits.llm_teacher)))

    setattr(mod, "_STUDENT_INFLIGHT", {})
    setattr(mod, "_STUDENT_INFLIGHT_LOCK", threading.Lock())

    setattr(mod, "_PROFILE_CACHE", {})
    setattr(mod, "_PROFILE_CACHE_LOCK", threading.Lock())
    setattr(mod, "_ASSIGNMENT_DETAIL_CACHE", {})
    setattr(mod, "_ASSIGNMENT_DETAIL_CACHE_LOCK", threading.Lock())

    setattr(mod, "_PROFILE_UPDATE_QUEUE", deque())
    setattr(mod, "_PROFILE_UPDATE_LOCK", threading.Lock())
    setattr(mod, "_PROFILE_UPDATE_EVENT", threading.Event())
    setattr(mod, "_PROFILE_UPDATE_WORKER_STARTED", False)

    setattr(mod, "_TEACHER_SESSION_COMPACT_TS", {})
    setattr(mod, "_TEACHER_SESSION_COMPACT_LOCK", threading.Lock())
    setattr(mod, "_SESSION_INDEX_LOCKS", {})
    setattr(mod, "_SESSION_INDEX_LOCKS_LOCK", threading.Lock())

    # Ensure diagnostics can be per-tenant if enabled.
    setattr(mod, "DIAG_LOG_PATH", uploads_dir / "diagnostics.log")
    setattr(mod, "_DIAG_LOGGER", None)

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
