from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExamWorkerDeps:
    job_queue: Deque[str]
    job_lock: Any
    job_event: Any
    job_dir: Path
    stop_event: Any
    worker_started_get: Callable[[], bool]
    worker_started_set: Callable[[bool], None]
    worker_thread_get: Callable[[], Any]
    worker_thread_set: Callable[[Any], None]
    process_job: Callable[[str], None]
    write_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    diag_log: Callable[[str, Dict[str, Any]], None]
    sleep: Callable[[float], None]
    thread_factory: Callable[..., Any]
    rq_enabled: Callable[[], bool]


def enqueue_exam_job_inline(job_id: str, *, deps: ExamWorkerDeps) -> None:
    with deps.job_lock:
        if job_id not in deps.job_queue:
            deps.job_queue.append(job_id)
    deps.job_event.set()


def scan_pending_exam_jobs_inline(*, deps: ExamWorkerDeps) -> int:
    deps.job_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for job_path in deps.job_dir.glob("*/job.json"):
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            _log.warning("corrupt job.json at %s, skipping", job_path, exc_info=True)
            continue
        status = str(data.get("status") or "")
        job_id = str(data.get("job_id") or "")
        if status in {"queued", "processing"} and job_id:
            enqueue_exam_job_inline(job_id, deps=deps)
            count += 1
    return count


def exam_job_worker_loop(*, deps: ExamWorkerDeps) -> None:
    while not deps.stop_event.is_set():
        deps.job_event.wait(timeout=0.1)
        if deps.stop_event.is_set():
            break
        job_id = ""
        with deps.job_lock:
            if deps.job_queue:
                job_id = deps.job_queue.popleft()
            if not deps.job_queue:
                deps.job_event.clear()
        if not job_id:
            deps.sleep(0.1)
            continue
        try:
            deps.process_job(job_id)
        except Exception as exc:
            deps.diag_log("exam_upload.job.failed", {"job_id": job_id, "error": str(exc)[:200]})
            deps.write_job(
                job_id,
                {
                    "status": "failed",
                    "error": str(exc)[:200],
                },
            )


def start_exam_upload_worker(*, deps: ExamWorkerDeps) -> None:
    if deps.rq_enabled():
        return
    if deps.worker_started_get():
        return
    deps.stop_event.clear()
    scan_pending_exam_jobs_inline(deps=deps)
    thread = deps.thread_factory(target=lambda: exam_job_worker_loop(deps=deps), daemon=True, name="exam-upload-worker")
    thread.start()
    deps.worker_thread_set(thread)
    deps.worker_started_set(True)


def stop_exam_upload_worker(*, deps: ExamWorkerDeps, timeout_sec: float = 1.5) -> None:
    if deps.rq_enabled():
        return
    deps.stop_event.set()
    deps.job_event.set()
    thread = deps.worker_thread_get()
    if thread is not None:
        try:
            thread.join(max(0.0, float(timeout_sec or 0.0)))
        except Exception:
            pass
    deps.worker_thread_set(None)
    deps.worker_started_set(False)
