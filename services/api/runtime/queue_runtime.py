from __future__ import annotations

from typing import Callable, Optional

from services.api import settings
from services.api.queue.queue_backend import get_queue_backend
from services.api.queue.queue_backend_factory import get_app_queue_backend


def app_queue_backend(*, tenant_id, is_pytest: bool, inline_backend_factory):
    return get_app_queue_backend(
        tenant_id=tenant_id,
        is_pytest=is_pytest,
        inline_backend_factory=inline_backend_factory,
    )


def enqueue_upload_job(job_id: str, *, backend) -> None:
    backend.enqueue_upload_job(job_id)


def enqueue_exam_job(job_id: str, *, backend) -> None:
    backend.enqueue_exam_job(job_id)


def enqueue_profile_update(payload: dict, *, backend) -> None:
    backend.enqueue_profile_update(payload)


def enqueue_chat_job(job_id: str, lane_id=None, *, backend):
    return backend.enqueue_chat_job(job_id, lane_id=lane_id)


def scan_pending_upload_jobs(*, backend) -> int:
    return int(backend.scan_pending_upload_jobs() or 0)


def scan_pending_exam_jobs(*, backend) -> int:
    return int(backend.scan_pending_exam_jobs() or 0)


def scan_pending_chat_jobs(*, backend) -> int:
    return int(backend.scan_pending_chat_jobs() or 0)


def start_runtime(
    *,
    backend=None,
    require_redis: Optional[Callable[[], None]] = None,
    is_pytest: Optional[bool] = None,
) -> None:
    if backend is None:
        backend = get_queue_backend(tenant_id=settings.tenant_id() or None)
    if is_pytest is None:
        is_pytest = settings.is_pytest()
    # Only require Redis when using the RQ backend (not inline/dev mode)
    if not is_pytest and not str(getattr(backend, "name", "")).startswith("inline"):
        if require_redis is None:
            from services.api.workers import rq_tasks

            require_redis = rq_tasks.require_redis
        require_redis()
    backend.start()


def stop_runtime(*, backend=None) -> None:
    if backend is None:
        backend = get_queue_backend(tenant_id=settings.tenant_id() or None)
    backend.stop()
