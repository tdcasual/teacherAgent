from __future__ import annotations

from typing import Any

from services.api import settings
from services.api.runtime.inline_backend_factory import build_inline_backend
from services.api.runtime.runtime_manager import RuntimeManagerDeps, start_tenant_runtime, stop_tenant_runtime
from services.api.teacher_provider_registry_service import validate_master_key_policy
from services.api.workers import (
    chat_worker_service,
    exam_worker_service,
    profile_update_worker_service,
    upload_worker_service,
)
from services.api.workers.inline_runtime import start_inline_workers, stop_inline_workers


def build_inline_backend_for_app(app_mod: Any) -> Any:
    upload_deps = app_mod.upload_worker_deps()
    exam_deps = app_mod.exam_worker_deps()
    profile_deps = app_mod.profile_update_worker_deps()
    chat_deps = app_mod.chat_worker_deps()
    profile_update_async = bool(getattr(app_mod, "PROFILE_UPDATE_ASYNC", False))

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
    return RuntimeManagerDeps(
        tenant_id=getattr(app_mod, "TENANT_ID", None) or None,
        is_pytest=settings.is_pytest(),
        validate_master_key_policy=validate_master_key_policy,
        inline_backend_factory=lambda: build_inline_backend_for_app(app_mod),
    )


def start_runtime(*, app_mod: Any | None = None) -> None:
    active_app_mod = app_mod
    if active_app_mod is None:
        from services.api import app as default_app_mod

        active_app_mod = default_app_mod
    start_tenant_runtime(deps=build_runtime_deps(active_app_mod))


def stop_runtime(*, app_mod: Any | None = None) -> None:
    active_app_mod = app_mod
    if active_app_mod is None:
        from services.api import app as default_app_mod

        active_app_mod = default_app_mod
    stop_tenant_runtime(deps=build_runtime_deps(active_app_mod))
