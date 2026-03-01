import threading
from collections import deque

from services.api.workers import (
    exam_worker_service,
    profile_update_worker_service,
    upload_worker_service,
)


class _AliveThread:
    def __init__(self, *, alive: bool = True):
        self._alive = alive
        self.join_calls = 0
        self.last_timeout = None

    def join(self, timeout=None):
        self.join_calls += 1
        self.last_timeout = timeout

    def is_alive(self):
        return self._alive


class _StartableThread:
    def __init__(self, *, target=None, daemon=None, name=None):
        self.target = target
        self.daemon = daemon
        self.name = name
        self.started = False
        self._alive = False

    def start(self):
        self.started = True
        self._alive = True

    def is_alive(self):
        return self._alive


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


def test_stop_upload_worker_keeps_started_when_thread_still_alive(tmp_path):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    worker_thread = _AliveThread(alive=True)
    holder = {"thread": worker_thread}

    deps = upload_worker_service.UploadWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=stop_event,
        worker_started_get=lambda: started["value"],
        worker_started_set=lambda value: started.__setitem__("value", bool(value)),
        worker_thread_get=lambda: holder["thread"],
        worker_thread_set=lambda value: holder.__setitem__("thread", value),
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
    )

    upload_worker_service.stop_upload_worker(deps=deps, timeout_sec=0.01)

    assert stop_event.is_set() is True
    assert event.is_set() is True
    assert started["value"] is True
    assert holder["thread"] is worker_thread


def test_stop_exam_worker_keeps_started_when_thread_still_alive(tmp_path):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    worker_thread = _AliveThread(alive=True)
    holder = {"thread": worker_thread}

    deps = exam_worker_service.ExamWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=stop_event,
        worker_started_get=lambda: started["value"],
        worker_started_set=lambda value: started.__setitem__("value", bool(value)),
        worker_thread_get=lambda: holder["thread"],
        worker_thread_set=lambda value: holder.__setitem__("thread", value),
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
    )

    exam_worker_service.stop_exam_upload_worker(deps=deps, timeout_sec=0.01)

    assert stop_event.is_set() is True
    assert event.is_set() is True
    assert started["value"] is True
    assert holder["thread"] is worker_thread


def test_stop_profile_update_worker_keeps_started_when_thread_still_alive():
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    worker_thread = _AliveThread(alive=True)
    holder = {"thread": worker_thread}

    deps = profile_update_worker_service.ProfileUpdateWorkerDeps(
        update_queue=queue,
        update_lock=lock,
        update_event=event,
        stop_event=stop_event,
        worker_started_get=lambda: started["value"],
        worker_started_set=lambda value: started.__setitem__("value", bool(value)),
        worker_thread_get=lambda: holder["thread"],
        worker_thread_set=lambda value: holder.__setitem__("thread", value),
        queue_max=32,
        student_profile_update=lambda _payload: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
        monotonic=lambda: 0.0,
    )

    profile_update_worker_service.stop_profile_update_worker(deps=deps, timeout_sec=0.01)

    assert stop_event.is_set() is True
    assert event.is_set() is True
    assert started["value"] is True
    assert holder["thread"] is worker_thread


def test_start_upload_worker_recovers_from_stale_started_flag(tmp_path):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    stale_thread = _AliveThread(alive=False)
    holder = {"thread": stale_thread}
    created_threads = []

    def _factory(*_args, **kwargs):
        thread = _StartableThread(**kwargs)
        created_threads.append(thread)
        return thread

    deps = upload_worker_service.UploadWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=stop_event,
        worker_started_get=lambda: started["value"],
        worker_started_set=lambda value: started.__setitem__("value", bool(value)),
        worker_thread_get=lambda: holder["thread"],
        worker_thread_set=lambda value: holder.__setitem__("thread", value),
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=_factory,
        rq_enabled=lambda: False,
    )

    upload_worker_service.start_upload_worker(deps=deps)

    assert started["value"] is True
    assert len(created_threads) == 1
    assert created_threads[0].started is True
    assert holder["thread"] is created_threads[0]


def test_start_exam_worker_recovers_from_stale_started_flag(tmp_path):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    stale_thread = _AliveThread(alive=False)
    holder = {"thread": stale_thread}
    created_threads = []

    def _factory(*_args, **kwargs):
        thread = _StartableThread(**kwargs)
        created_threads.append(thread)
        return thread

    deps = exam_worker_service.ExamWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=stop_event,
        worker_started_get=lambda: started["value"],
        worker_started_set=lambda value: started.__setitem__("value", bool(value)),
        worker_thread_get=lambda: holder["thread"],
        worker_thread_set=lambda value: holder.__setitem__("thread", value),
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=_factory,
        rq_enabled=lambda: False,
    )

    exam_worker_service.start_exam_upload_worker(deps=deps)

    assert started["value"] is True
    assert len(created_threads) == 1
    assert created_threads[0].started is True
    assert holder["thread"] is created_threads[0]


def test_start_profile_update_worker_recovers_from_stale_started_flag():
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    stale_thread = _AliveThread(alive=False)
    holder = {"thread": stale_thread}
    created_threads = []

    def _factory(*_args, **kwargs):
        thread = _StartableThread(**kwargs)
        created_threads.append(thread)
        return thread

    deps = profile_update_worker_service.ProfileUpdateWorkerDeps(
        update_queue=queue,
        update_lock=lock,
        update_event=event,
        stop_event=stop_event,
        worker_started_get=lambda: started["value"],
        worker_started_set=lambda value: started.__setitem__("value", bool(value)),
        worker_thread_get=lambda: holder["thread"],
        worker_thread_set=lambda value: holder.__setitem__("thread", value),
        queue_max=32,
        student_profile_update=lambda _payload: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=_factory,
        rq_enabled=lambda: False,
        monotonic=lambda: 0.0,
    )

    profile_update_worker_service.start_profile_update_worker(deps=deps)

    assert started["value"] is True
    assert len(created_threads) == 1
    assert created_threads[0].started is True
    assert holder["thread"] is created_threads[0]
