import threading
from collections import deque

import pytest

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


def test_scan_pending_upload_jobs_inline_counts_only_new_enqueues(tmp_path):
    queue = deque(["job-1"])
    lock = threading.Lock()
    event = threading.Event()
    (tmp_path / "job-1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "job-1" / "job.json").write_text('{"status":"queued","job_id":"job-1"}\n', encoding="utf-8")

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

    count = upload_worker_service.scan_pending_upload_jobs_inline(deps=deps)
    assert count == 0
    assert list(queue) == ["job-1"]


def test_scan_pending_exam_jobs_inline_counts_only_new_enqueues(tmp_path):
    queue = deque(["exam-1"])
    lock = threading.Lock()
    event = threading.Event()
    (tmp_path / "exam-1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "exam-1" / "job.json").write_text('{"status":"queued","job_id":"exam-1"}\n', encoding="utf-8")

    deps = exam_worker_service.ExamWorkerDeps(
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

    count = exam_worker_service.scan_pending_exam_jobs_inline(deps=deps)
    assert count == 0
    assert list(queue) == ["exam-1"]


def test_upload_worker_loop_rejects_legacy_event_wait_without_timeout(tmp_path):
    queue = deque()
    lock = threading.Lock()
    stop_event = threading.Event()

    class _LegacyEvent:
        def __init__(self):
            self.wait_calls = 0

        def set(self):
            return None

        def clear(self):
            return None

        def wait(self):
            self.wait_calls += 1
            stop_event.set()
            return False

    event = _LegacyEvent()
    deps = upload_worker_service.UploadWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=stop_event,
        worker_started_get=lambda: True,
        worker_started_set=lambda _value: None,
        worker_thread_get=lambda: None,
        worker_thread_set=lambda _value: None,
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
    )

    with pytest.raises(TypeError):
        upload_worker_service.upload_job_worker_loop(deps=deps)
    assert event.wait_calls == 0


def test_exam_worker_loop_rejects_legacy_event_wait_without_timeout(tmp_path):
    queue = deque()
    lock = threading.Lock()
    stop_event = threading.Event()

    class _LegacyEvent:
        def __init__(self):
            self.wait_calls = 0

        def set(self):
            return None

        def clear(self):
            return None

        def wait(self):
            self.wait_calls += 1
            stop_event.set()
            return False

    event = _LegacyEvent()
    deps = exam_worker_service.ExamWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=stop_event,
        worker_started_get=lambda: True,
        worker_started_set=lambda _value: None,
        worker_thread_get=lambda: None,
        worker_thread_set=lambda _value: None,
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
    )

    with pytest.raises(TypeError):
        exam_worker_service.exam_job_worker_loop(deps=deps)
    assert event.wait_calls == 0


def test_profile_update_worker_loop_rejects_legacy_event_wait_without_timeout():
    queue = deque()
    lock = threading.Lock()
    stop_event = threading.Event()

    class _LegacyEvent:
        def __init__(self):
            self.wait_calls = 0

        def set(self):
            return None

        def clear(self):
            return None

        def wait(self):
            self.wait_calls += 1
            stop_event.set()
            return False

    event = _LegacyEvent()
    deps = profile_update_worker_service.ProfileUpdateWorkerDeps(
        update_queue=queue,
        update_lock=lock,
        update_event=event,
        stop_event=stop_event,
        worker_started_get=lambda: True,
        worker_started_set=lambda _value: None,
        worker_thread_get=lambda: None,
        worker_thread_set=lambda _value: None,
        queue_max=32,
        student_profile_update=lambda _payload: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
        monotonic=lambda: 0.0,
    )

    with pytest.raises(TypeError):
        profile_update_worker_service.profile_update_worker_loop(deps=deps)
    assert event.wait_calls == 0


def test_upload_worker_loop_rejects_uninspectable_wait_callable_without_timeout(tmp_path):
    queue = deque()
    lock = threading.Lock()
    stop_event = threading.Event()

    class _WaitCallable:
        def __init__(self):
            self.calls = 0

        @property
        def __signature__(self):
            raise ValueError("signature unavailable")

        def __call__(self):
            self.calls += 1
            stop_event.set()
            return False

    class _Event:
        def __init__(self):
            self.wait = _WaitCallable()

        def set(self):
            return None

        def clear(self):
            return None

    event = _Event()
    deps = upload_worker_service.UploadWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=stop_event,
        worker_started_get=lambda: True,
        worker_started_set=lambda _value: None,
        worker_thread_get=lambda: None,
        worker_thread_set=lambda _value: None,
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
    )

    with pytest.raises(TypeError):
        upload_worker_service.upload_job_worker_loop(deps=deps)
    assert event.wait.calls == 0


def test_exam_worker_loop_rejects_uninspectable_wait_callable_without_timeout(tmp_path):
    queue = deque()
    lock = threading.Lock()
    stop_event = threading.Event()

    class _WaitCallable:
        def __init__(self):
            self.calls = 0

        @property
        def __signature__(self):
            raise ValueError("signature unavailable")

        def __call__(self):
            self.calls += 1
            stop_event.set()
            return False

    class _Event:
        def __init__(self):
            self.wait = _WaitCallable()

        def set(self):
            return None

        def clear(self):
            return None

    event = _Event()
    deps = exam_worker_service.ExamWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=stop_event,
        worker_started_get=lambda: True,
        worker_started_set=lambda _value: None,
        worker_thread_get=lambda: None,
        worker_thread_set=lambda _value: None,
        process_job=lambda _job_id: None,
        write_job=lambda _job_id, _updates: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
    )

    with pytest.raises(TypeError):
        exam_worker_service.exam_job_worker_loop(deps=deps)
    assert event.wait.calls == 0


def test_profile_worker_loop_rejects_uninspectable_wait_callable_without_timeout():
    queue = deque()
    lock = threading.Lock()
    stop_event = threading.Event()

    class _WaitCallable:
        def __init__(self):
            self.calls = 0

        @property
        def __signature__(self):
            raise ValueError("signature unavailable")

        def __call__(self):
            self.calls += 1
            stop_event.set()
            return False

    class _Event:
        def __init__(self):
            self.wait = _WaitCallable()

        def set(self):
            return None

        def clear(self):
            return None

    event = _Event()
    deps = profile_update_worker_service.ProfileUpdateWorkerDeps(
        update_queue=queue,
        update_lock=lock,
        update_event=event,
        stop_event=stop_event,
        worker_started_get=lambda: True,
        worker_started_set=lambda _value: None,
        worker_thread_get=lambda: None,
        worker_thread_set=lambda _value: None,
        queue_max=32,
        student_profile_update=lambda _payload: {},
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
        monotonic=lambda: 0.0,
    )

    with pytest.raises(TypeError):
        profile_update_worker_service.profile_update_worker_loop(deps=deps)
    assert event.wait.calls == 0


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


def test_stop_upload_worker_extends_join_timeout_under_pytest(tmp_path, monkeypatch):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    worker_thread = _AliveThread(alive=False)
    holder = {"thread": worker_thread}
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_inline_worker_services.py::test_upload (call)")

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

    assert worker_thread.join_calls == 1
    assert float(worker_thread.last_timeout or 0.0) >= 4.9
    assert started["value"] is False


def test_stop_exam_worker_extends_join_timeout_under_pytest(tmp_path, monkeypatch):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    worker_thread = _AliveThread(alive=False)
    holder = {"thread": worker_thread}
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_inline_worker_services.py::test_exam (call)")

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

    assert worker_thread.join_calls == 1
    assert float(worker_thread.last_timeout or 0.0) >= 4.9
    assert started["value"] is False


def test_stop_profile_update_worker_extends_join_timeout_under_pytest(monkeypatch):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": True}
    worker_thread = _AliveThread(alive=False)
    holder = {"thread": worker_thread}
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_inline_worker_services.py::test_profile (call)")

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

    assert worker_thread.join_calls == 1
    assert float(worker_thread.last_timeout or 0.0) >= 4.9
    assert started["value"] is False


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
