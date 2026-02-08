from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from . import settings
from .queue_backend_inline import InlineQueueBackend
from .queue_backend_rq import RqQueueBackend


class QueueBackend(Protocol):
    name: str

    def enqueue_upload_job(self, job_id: str) -> None: ...
    def enqueue_exam_job(self, job_id: str) -> None: ...
    def enqueue_profile_update(self, payload: Dict[str, Any]) -> None: ...
    def enqueue_chat_job(self, job_id: str, lane_id: Optional[str] = None) -> Dict[str, Any]: ...
    def scan_pending_upload_jobs(self) -> int: ...
    def scan_pending_exam_jobs(self) -> int: ...
    def scan_pending_chat_jobs(self) -> int: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...


def rq_enabled() -> bool:
    if settings.rq_backend_enabled():
        return True
    return settings.job_queue_backend() in {"rq", "redis", "redis-rq"}


def get_queue_backend(
    *,
    tenant_id: Optional[str] = None,
    inline_backend: Optional[QueueBackend] = None,
) -> QueueBackend:
    if rq_enabled():
        return RqQueueBackend(tenant_id=tenant_id)
    raise RuntimeError("RQ backend required")
