from __future__ import annotations

from services.api.queue.queue_inline_backend import InlineQueueBackend


def build_inline_backend(
    *,
    enqueue_upload_job_fn,
    enqueue_exam_job_fn,
    enqueue_profile_update_fn,
    enqueue_chat_job_fn,
    scan_pending_upload_jobs_fn,
    scan_pending_exam_jobs_fn,
    scan_pending_chat_jobs_fn,
    start_fn,
    stop_fn,
):
    return InlineQueueBackend(
        enqueue_upload_job_fn=enqueue_upload_job_fn,
        enqueue_exam_job_fn=enqueue_exam_job_fn,
        enqueue_profile_update_fn=enqueue_profile_update_fn,
        enqueue_chat_job_fn=enqueue_chat_job_fn,
        scan_pending_upload_jobs_fn=scan_pending_upload_jobs_fn,
        scan_pending_exam_jobs_fn=scan_pending_exam_jobs_fn,
        scan_pending_chat_jobs_fn=scan_pending_chat_jobs_fn,
        start_fn=start_fn,
        stop_fn=stop_fn,
    )
