from collections import deque
import threading

from services.api.workers import upload_worker_service


def test_upload_inline_enqueue_sets_event(tmp_path):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()

    deps = upload_worker_service.UploadWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=threading.Event(),
        worker_started_get=lambda: False,
        worker_started_set=lambda _: None,
        worker_thread_get=lambda: None,
        worker_thread_set=lambda _value: None,
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
    )

    upload_worker_service.enqueue_upload_job_inline("job-1", deps=deps)
    assert "job-1" in list(queue)
    assert event.is_set() is True
