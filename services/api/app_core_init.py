from __future__ import annotations

from typing import Any


def build_inline_backend_factory(
    *,
    current_core: Any,
    app_core_wiring_exports_module: Any,
    core_service_imports_module: Any,
    profile_update_async: bool,
) -> Any:
    upload_deps = app_core_wiring_exports_module.upload_worker_deps(current_core)
    exam_deps = app_core_wiring_exports_module.exam_worker_deps(current_core)
    profile_deps = app_core_wiring_exports_module.profile_update_worker_deps(current_core)
    chat_deps = app_core_wiring_exports_module.chat_worker_deps(current_core)
    return core_service_imports_module.build_inline_backend(
        enqueue_upload_job_fn=lambda job_id: core_service_imports_module.upload_worker_service.enqueue_upload_job_inline(
            job_id, deps=upload_deps
        ),
        enqueue_exam_job_fn=lambda job_id: core_service_imports_module.exam_worker_service.enqueue_exam_job_inline(
            job_id, deps=exam_deps
        ),
        enqueue_profile_update_fn=lambda payload: core_service_imports_module.profile_update_worker_service.enqueue_profile_update_inline(
            payload, deps=profile_deps
        ),
        enqueue_chat_job_fn=lambda job_id, lane_id=None: core_service_imports_module._enqueue_chat_job_impl(
            job_id, deps=chat_deps, lane_id=lane_id
        ),
        scan_pending_upload_jobs_fn=lambda: core_service_imports_module.upload_worker_service.scan_pending_upload_jobs_inline(
            deps=upload_deps
        ),
        scan_pending_exam_jobs_fn=lambda: core_service_imports_module.exam_worker_service.scan_pending_exam_jobs_inline(
            deps=exam_deps
        ),
        scan_pending_chat_jobs_fn=lambda: core_service_imports_module._scan_pending_chat_jobs_impl(deps=chat_deps),
        start_fn=lambda: core_service_imports_module.start_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=profile_update_async,
        ),
        stop_fn=lambda: core_service_imports_module.stop_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=profile_update_async,
        ),
    )
