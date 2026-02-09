from __future__ import annotations

from typing import Any, Dict, Optional

def _rq_tasks():
    from services.api import rq_tasks

    return rq_tasks


class RqQueueBackend:
    name = "rq"

    def __init__(self, *, tenant_id: Optional[str] = None):
        self.tenant_id = tenant_id

    def enqueue_upload_job(self, job_id: str) -> None:
        _rq_tasks().enqueue_upload_job(job_id, tenant_id=self.tenant_id)

    def enqueue_exam_job(self, job_id: str) -> None:
        _rq_tasks().enqueue_exam_job(job_id, tenant_id=self.tenant_id)

    def enqueue_profile_update(self, payload: Dict[str, Any]) -> None:
        _rq_tasks().enqueue_profile_update(payload, tenant_id=self.tenant_id)

    def enqueue_chat_job(self, job_id: str, lane_id: Optional[str] = None) -> Dict[str, Any]:
        return _rq_tasks().enqueue_chat_job(job_id, lane_id=lane_id, tenant_id=self.tenant_id)

    def scan_pending_upload_jobs(self) -> int:
        return _rq_tasks().scan_pending_upload_jobs(tenant_id=self.tenant_id)

    def scan_pending_exam_jobs(self) -> int:
        return _rq_tasks().scan_pending_exam_jobs(tenant_id=self.tenant_id)

    def scan_pending_chat_jobs(self) -> int:
        return _rq_tasks().scan_pending_chat_jobs(tenant_id=self.tenant_id)

    def start(self) -> None:
        return

    def stop(self) -> None:
        return
