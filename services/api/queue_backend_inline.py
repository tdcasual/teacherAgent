from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class InlineQueueBackend:
    name = "inline"

    def __init__(
        self,
        *,
        enqueue_upload_job: Optional[Callable[[str], None]] = None,
        enqueue_exam_job: Optional[Callable[[str], None]] = None,
        enqueue_profile_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        enqueue_chat_job: Optional[Callable[[str, Optional[str]], Dict[str, Any]]] = None,
        scan_pending_upload_jobs: Optional[Callable[[], int]] = None,
        scan_pending_exam_jobs: Optional[Callable[[], int]] = None,
        scan_pending_chat_jobs: Optional[Callable[[], int]] = None,
        start: Optional[Callable[[], None]] = None,
        stop: Optional[Callable[[], None]] = None,
    ):
        self._enqueue_upload_job = enqueue_upload_job
        self._enqueue_exam_job = enqueue_exam_job
        self._enqueue_profile_update = enqueue_profile_update
        self._enqueue_chat_job = enqueue_chat_job
        self._scan_pending_upload_jobs = scan_pending_upload_jobs
        self._scan_pending_exam_jobs = scan_pending_exam_jobs
        self._scan_pending_chat_jobs = scan_pending_chat_jobs
        self._start = start
        self._stop = stop

    def _require(self, fn: Optional[Callable[..., Any]], name: str) -> Callable[..., Any]:
        if fn is None:
            raise RuntimeError(f"InlineQueueBackend missing {name}")
        return fn

    def enqueue_upload_job(self, job_id: str) -> None:
        self._require(self._enqueue_upload_job, "enqueue_upload_job")(job_id)

    def enqueue_exam_job(self, job_id: str) -> None:
        self._require(self._enqueue_exam_job, "enqueue_exam_job")(job_id)

    def enqueue_profile_update(self, payload: Dict[str, Any]) -> None:
        self._require(self._enqueue_profile_update, "enqueue_profile_update")(payload)

    def enqueue_chat_job(self, job_id: str, lane_id: Optional[str] = None) -> Dict[str, Any]:
        return self._require(self._enqueue_chat_job, "enqueue_chat_job")(job_id, lane_id)

    def scan_pending_upload_jobs(self) -> int:
        return int(self._require(self._scan_pending_upload_jobs, "scan_pending_upload_jobs")() or 0)

    def scan_pending_exam_jobs(self) -> int:
        return int(self._require(self._scan_pending_exam_jobs, "scan_pending_exam_jobs")() or 0)

    def scan_pending_chat_jobs(self) -> int:
        return int(self._require(self._scan_pending_chat_jobs, "scan_pending_chat_jobs")() or 0)

    def start(self) -> None:
        if self._start is not None:
            self._start()

    def stop(self) -> None:
        if self._stop is not None:
            self._stop()
