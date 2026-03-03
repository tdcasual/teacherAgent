from __future__ import annotations

import sys
from typing import Any

from services.api import settings
from services.api.runtime.inline_backend_factory import build_inline_backend
from services.api.runtime.runtime_manager import (
    RuntimeManagerDeps,
    start_tenant_runtime,
    stop_tenant_runtime,
)
from services.api.teacher_provider_registry_service import validate_master_key_policy
from services.api.workers import (
    chat_worker_service,
    exam_worker_service,
    profile_update_worker_service,
    upload_worker_service,
)
from services.api.workers.inline_runtime import start_inline_workers, stop_inline_workers


def _resolve_app_core(app_mod: Any) -> Any:
    state = getattr(app_mod, "state", None)
    core = getattr(state, "core", None) if state is not None else None
    if core is not None:
        return core

    getter = getattr(app_mod, "get_core", None)
    if callable(getter):
        try:
            core = getter()
            if core is not None:
                return core
        except Exception:
            pass
    app_obj = getattr(app_mod, "app", None)
    state = getattr(app_obj, "state", None) if app_obj is not None else None
    core = getattr(state, "core", None) if state is not None else None
    if core is not None:
        return core
    return app_mod


def build_inline_backend_for_app(app_mod: Any) -> Any:
    core = _resolve_app_core(app_mod)
    upload_deps = core.upload_worker_deps()
    exam_deps = core.exam_worker_deps()
    profile_deps = core.profile_update_worker_deps()
    chat_deps = core.chat_worker_deps()
    profile_update_async = bool(getattr(core, "PROFILE_UPDATE_ASYNC", False))

    return build_inline_backend(
        enqueue_upload_job_fn=lambda job_id: upload_worker_service.enqueue_upload_job_inline(
            job_id, deps=upload_deps
        ),
        enqueue_exam_job_fn=lambda job_id: exam_worker_service.enqueue_exam_job_inline(job_id, deps=exam_deps),
        enqueue_profile_update_fn=lambda payload: profile_update_worker_service.enqueue_profile_update_inline(
            payload, deps=profile_deps
        ),
        enqueue_chat_job_fn=lambda job_id, lane_id=None: chat_worker_service.enqueue_chat_job(
            job_id, deps=chat_deps, lane_id=lane_id
        ),
        scan_pending_upload_jobs_fn=lambda: upload_worker_service.scan_pending_upload_jobs_inline(
            deps=upload_deps
        ),
        scan_pending_exam_jobs_fn=lambda: exam_worker_service.scan_pending_exam_jobs_inline(deps=exam_deps),
        scan_pending_chat_jobs_fn=lambda: chat_worker_service.scan_pending_chat_jobs(deps=chat_deps),
        start_fn=lambda: start_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=profile_update_async,
        ),
        stop_fn=lambda: stop_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=profile_update_async,
        ),
    )


def build_runtime_deps(app_mod: Any) -> RuntimeManagerDeps:
    core = _resolve_app_core(app_mod)
    return RuntimeManagerDeps(
        tenant_id=getattr(core, "TENANT_ID", None) or None,
        is_pytest=bool(getattr(getattr(core, "_settings", None), "is_pytest", settings.is_pytest)()),
        validate_master_key_policy=validate_master_key_policy,
        inline_backend_factory=lambda: build_inline_backend_for_app(core),
    )


def _default_app_module() -> Any:
    # Prefer sys.modules entry to avoid stale package attributes in reload-heavy tests.
    mod = sys.modules.get("services.api.app")
    if mod is not None:
        return mod
    from services.api import app as default_app_mod

    return default_app_mod


def start_runtime(*, app_mod: Any | None = None) -> None:
    active_app_mod = app_mod if app_mod is not None else _default_app_module()
    start_tenant_runtime(deps=build_runtime_deps(active_app_mod))


def stop_runtime(*, app_mod: Any | None = None) -> None:
    active_app_mod = app_mod if app_mod is not None else _default_app_module()
    stop_tenant_runtime(deps=build_runtime_deps(active_app_mod))
