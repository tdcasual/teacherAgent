from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class InlineQueueBackend:
    enqueue_upload_job_fn: Callable[[str], None]
    enqueue_exam_job_fn: Callable[[str], None]
    enqueue_profile_update_fn: Callable[[Dict[str, Any]], None]
    enqueue_chat_job_fn: Callable[[str, Optional[str]], Dict[str, Any]]
    scan_pending_upload_jobs_fn: Callable[[], int]
    scan_pending_exam_jobs_fn: Callable[[], int]
    scan_pending_chat_jobs_fn: Callable[[], int]
    start_fn: Callable[[], None]
    stop_fn: Callable[[], None]
    name: str = "inline-test"

    def enqueue_upload_job(self, job_id: str) -> None:
        return self.enqueue_upload_job_fn(job_id)

    def enqueue_exam_job(self, job_id: str) -> None:
        return self.enqueue_exam_job_fn(job_id)

    def enqueue_profile_update(self, payload: Dict[str, Any]) -> None:
        return self.enqueue_profile_update_fn(payload)

    def enqueue_chat_job(self, job_id: str, lane_id: Optional[str] = None) -> Dict[str, Any]:
        return self.enqueue_chat_job_fn(job_id, lane_id)

    def scan_pending_upload_jobs(self) -> int:
        return int(self.scan_pending_upload_jobs_fn() or 0)

    def scan_pending_exam_jobs(self) -> int:
        return int(self.scan_pending_exam_jobs_fn() or 0)

    def scan_pending_chat_jobs(self) -> int:
        return int(self.scan_pending_chat_jobs_fn() or 0)

    def start(self) -> None:
        return self.start_fn()

    def stop(self) -> None:
        return self.stop_fn()
