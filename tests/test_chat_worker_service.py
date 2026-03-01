from __future__ import annotations

import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.workers.chat_worker_service import (
    ChatWorkerDeps,
    chat_job_worker_loop,
    enqueue_chat_job,
    start_chat_worker,
    stop_chat_worker,
)


class _FakeEvent:
    def __init__(self):
        self.set_calls = 0
        self.clear_calls = 0

    def set(self):
        self.set_calls += 1

    def clear(self):
        self.clear_calls += 1

    def wait(self):
        return None


class _FakeThread:
    def __init__(self, *args, **kwargs):
        self.started = False
        self.name = kwargs.get("name")

    def start(self):
        self.started = True


class _JoinAwareThread:
    def __init__(self, *, alive: bool):
        self._alive = alive
        self.join_calls = 0
        self.join_timeouts = []

    def start(self):
        return None

    def join(self, timeout=None):
        self.join_calls += 1
        self.join_timeouts.append(timeout)

    def is_alive(self):
        return self._alive


class ChatWorkerServiceTest(unittest.TestCase):
    def test_enqueue_chat_job_uses_resolved_lane_and_sets_event(self):
        lane_jobs = []
        event = _FakeEvent()

        def chat_enqueue_locked(job_id, lane_id):
            lane_jobs.append((job_id, lane_id))
            return len(lane_jobs)

        deps = ChatWorkerDeps(
            chat_job_dir=Path("."),
            chat_job_lock=threading.Lock(),
            chat_job_event=event,
            chat_worker_threads=[],
            chat_worker_pool_size=1,
            worker_started_get=lambda: False,
            worker_started_set=lambda value: None,
            load_chat_job=lambda job_id: {"job_id": job_id, "lane_id": "lane:t1"},
            write_chat_job=lambda job_id, updates: {"job_id": job_id, **updates},
            resolve_chat_lane_id_from_job=lambda job: str(job.get("lane_id") or "lane:fallback"),
            chat_enqueue_locked=chat_enqueue_locked,
            chat_lane_load_locked=lambda lane_id: {"queued": len(lane_jobs), "active": 0, "total": len(lane_jobs)},
            chat_pick_next_locked=lambda: ("", ""),
            chat_mark_done_locked=lambda job_id, lane_id: None,
            chat_has_pending_locked=lambda: False,
            process_chat_job=lambda job_id: None,
            diag_log=lambda *_args, **_kwargs: None,
            sleep=lambda _seconds: None,
            thread_factory=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
        )

        result = enqueue_chat_job("cjob_001", deps=deps)
        self.assertEqual(result["lane_id"], "lane:t1")
        self.assertEqual(result["lane_queue_position"], 1)
        self.assertEqual(result["lane_queue_size"], 1)
        self.assertEqual(event.set_calls, 1)

    def test_start_chat_worker_is_idempotent(self):
        with TemporaryDirectory() as td:
            started = {"value": False}
            threads = []
            event = _FakeEvent()

            deps = ChatWorkerDeps(
                chat_job_dir=Path(td) / "jobs",
                chat_job_lock=threading.Lock(),
                chat_job_event=event,
                chat_worker_threads=threads,
                chat_worker_pool_size=2,
                worker_started_get=lambda: started["value"],
                worker_started_set=lambda value: started.__setitem__("value", bool(value)),
                load_chat_job=lambda job_id: {"job_id": job_id},
                write_chat_job=lambda job_id, updates: {"job_id": job_id, **updates},
                resolve_chat_lane_id_from_job=lambda job: "lane:1",
                chat_enqueue_locked=lambda job_id, lane_id: 1,
                chat_lane_load_locked=lambda lane_id: {"queued": 1, "active": 0, "total": 1},
                chat_pick_next_locked=lambda: ("", ""),
                chat_mark_done_locked=lambda job_id, lane_id: None,
                chat_has_pending_locked=lambda: False,
                process_chat_job=lambda job_id: None,
                diag_log=lambda *_args, **_kwargs: None,
                sleep=lambda _seconds: None,
                thread_factory=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
            )

            start_chat_worker(deps=deps)
            start_chat_worker(deps=deps)

            self.assertTrue(started["value"])
            self.assertEqual(len(threads), 2)
            self.assertTrue(all(getattr(t, "started", False) for t in threads))

    def test_stop_chat_worker_keeps_started_flag_when_thread_still_alive(self):
        started = {"value": True}
        chat_worker_threads = [_JoinAwareThread(alive=True)]
        event = _FakeEvent()
        deps = ChatWorkerDeps(
            chat_job_dir=Path("."),
            chat_job_lock=threading.Lock(),
            chat_job_event=event,
            chat_worker_threads=chat_worker_threads,
            chat_worker_pool_size=1,
            worker_started_get=lambda: started["value"],
            worker_started_set=lambda value: started.__setitem__("value", bool(value)),
            load_chat_job=lambda job_id: {"job_id": job_id},
            write_chat_job=lambda job_id, updates: {"job_id": job_id, **updates},
            resolve_chat_lane_id_from_job=lambda job: "lane:test",
            chat_enqueue_locked=lambda job_id, lane_id: 1,
            chat_lane_load_locked=lambda lane_id: {"queued": 0, "active": 0, "total": 0},
            chat_pick_next_locked=lambda: ("", ""),
            chat_mark_done_locked=lambda job_id, lane_id: None,
            chat_has_pending_locked=lambda: False,
            process_chat_job=lambda job_id: None,
            diag_log=lambda *_args, **_kwargs: None,
            sleep=lambda _seconds: None,
            thread_factory=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
        )

        stop_chat_worker(deps=deps, timeout_sec=0.01)

        assert started["value"] is True
        assert len(chat_worker_threads) == 1
        assert event.set_calls == 1

    def test_start_chat_worker_recovers_from_stale_started_flag(self):
        with TemporaryDirectory() as td:
            started = {"value": True}
            stale_thread = _JoinAwareThread(alive=False)
            threads = [stale_thread]
            event = _FakeEvent()

            deps = ChatWorkerDeps(
                chat_job_dir=Path(td) / "jobs",
                chat_job_lock=threading.Lock(),
                chat_job_event=event,
                chat_worker_threads=threads,
                chat_worker_pool_size=1,
                worker_started_get=lambda: started["value"],
                worker_started_set=lambda value: started.__setitem__("value", bool(value)),
                load_chat_job=lambda job_id: {"job_id": job_id},
                write_chat_job=lambda job_id, updates: {"job_id": job_id, **updates},
                resolve_chat_lane_id_from_job=lambda job: "lane:1",
                chat_enqueue_locked=lambda job_id, lane_id: 1,
                chat_lane_load_locked=lambda lane_id: {"queued": 0, "active": 0, "total": 0},
                chat_pick_next_locked=lambda: ("", ""),
                chat_mark_done_locked=lambda job_id, lane_id: None,
                chat_has_pending_locked=lambda: False,
                process_chat_job=lambda job_id: None,
                diag_log=lambda *_args, **_kwargs: None,
                sleep=lambda _seconds: None,
                thread_factory=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
            )

            start_chat_worker(deps=deps)

            assert started["value"] is True
            assert len(threads) == 1
            assert isinstance(threads[0], _FakeThread)
            assert threads[0].started is True

    def test_start_chat_worker_respects_started_override_without_tracked_threads(self):
        with TemporaryDirectory() as td:
            started = {"value": True}
            threads = []
            created_threads = []
            event = _FakeEvent()

            def _factory(*args, **kwargs):
                thread = _FakeThread(*args, **kwargs)
                created_threads.append(thread)
                return thread

            deps = ChatWorkerDeps(
                chat_job_dir=Path(td) / "jobs",
                chat_job_lock=threading.Lock(),
                chat_job_event=event,
                chat_worker_threads=threads,
                chat_worker_pool_size=1,
                worker_started_get=lambda: started["value"],
                worker_started_set=lambda value: started.__setitem__("value", bool(value)),
                load_chat_job=lambda job_id: {"job_id": job_id},
                write_chat_job=lambda job_id, updates: {"job_id": job_id, **updates},
                resolve_chat_lane_id_from_job=lambda job: "lane:1",
                chat_enqueue_locked=lambda job_id, lane_id: 1,
                chat_lane_load_locked=lambda lane_id: {"queued": 0, "active": 0, "total": 0},
                chat_pick_next_locked=lambda: ("", ""),
                chat_mark_done_locked=lambda job_id, lane_id: None,
                chat_has_pending_locked=lambda: False,
                process_chat_job=lambda job_id: None,
                diag_log=lambda *_args, **_kwargs: None,
                sleep=lambda _seconds: None,
                thread_factory=_factory,
            )

            start_chat_worker(deps=deps)

            assert started["value"] is True
            assert created_threads == []
            assert threads == []


if __name__ == "__main__":
    unittest.main()


def test_chat_pick_next_locked_initializes_missing_state(monkeypatch):
    from services.api import chat_lane_repository as repo

    class _State:
        pass

    state = _State()
    monkeypatch.setattr(repo, "_get_state", lambda: state)

    job_id, lane_id = repo._chat_pick_next_locked()

    assert (job_id, lane_id) == ("", "")
    assert isinstance(state.CHAT_JOB_LANES, dict)
    assert isinstance(state.CHAT_JOB_ACTIVE_LANES, set)
    assert isinstance(state.CHAT_JOB_QUEUED, set)
    assert isinstance(state.CHAT_JOB_TO_LANE, dict)
    assert isinstance(state.CHAT_LANE_CURSOR, list)


def test_worker_loop_skips_pick_when_event_not_set(tmp_path):
    stop_event = threading.Event()
    pick_calls = {"count": 0}

    class _IdleEvent:
        def __init__(self):
            self.calls = 0

        def set(self):
            return None

        def clear(self):
            return None

        def wait(self, timeout=0.1):
            self.calls += 1
            if self.calls >= 2:
                stop_event.set()
            return False

    event = _IdleEvent()

    def _pick_next():
        pick_calls["count"] += 1
        return "", ""

    deps = ChatWorkerDeps(
        chat_job_dir=tmp_path / "jobs",
        chat_job_lock=threading.Lock(),
        chat_job_event=event,
        chat_worker_threads=[],
        chat_worker_pool_size=1,
        worker_started_get=lambda: True,
        worker_started_set=lambda value: None,
        load_chat_job=lambda job_id: {"job_id": job_id},
        write_chat_job=lambda job_id, updates: {"job_id": job_id, **updates},
        resolve_chat_lane_id_from_job=lambda job: "lane:test",
        chat_enqueue_locked=lambda job_id, lane_id: 1,
        chat_lane_load_locked=lambda lane_id: {"queued": 0, "active": 0, "total": 0},
        chat_pick_next_locked=_pick_next,
        chat_mark_done_locked=lambda job_id, lane_id: None,
        chat_has_pending_locked=lambda: False,
        process_chat_job=lambda job_id: None,
        diag_log=lambda *_args, **_kwargs: None,
        sleep=lambda _seconds: None,
        thread_factory=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
        stop_event=stop_event,
    )

    chat_job_worker_loop(deps=deps)
    assert pick_calls["count"] == 0


def test_worker_loop_marks_failed_and_emits_terminal_event_on_processing_error(tmp_path):
    stop_event = threading.Event()
    write_calls = []
    append_calls = []

    class _OneShotEvent:
        def __init__(self):
            self.calls = 0

        def set(self):
            return None

        def clear(self):
            return None

        def wait(self, timeout=0.1):
            self.calls += 1
            if self.calls == 1:
                return True
            stop_event.set()
            return False

    event = _OneShotEvent()

    picked = {"done": False}

    def _pick_next():
        if picked["done"]:
            return "", ""
        picked["done"] = True
        return "cjob_err_1", "lane:test"

    deps = ChatWorkerDeps(
        chat_job_dir=tmp_path / "jobs",
        chat_job_lock=threading.Lock(),
        chat_job_event=event,
        chat_worker_threads=[],
        chat_worker_pool_size=1,
        worker_started_get=lambda: True,
        worker_started_set=lambda value: None,
        load_chat_job=lambda job_id: {"job_id": job_id},
        write_chat_job=lambda job_id, updates: write_calls.append(
            {
                "job_id": str(job_id),
                "status": str((updates or {}).get("status") or ""),
                "error": str((updates or {}).get("error") or ""),
            }
        ),
        resolve_chat_lane_id_from_job=lambda job: "lane:test",
        chat_enqueue_locked=lambda job_id, lane_id: 1,
        chat_lane_load_locked=lambda lane_id: {"queued": 0, "active": 0, "total": 0},
        chat_pick_next_locked=_pick_next,
        chat_mark_done_locked=lambda job_id, lane_id: None,
        chat_has_pending_locked=lambda: False,
        process_chat_job=lambda _job_id: (_ for _ in ()).throw(RuntimeError("boom")),
        diag_log=lambda *_args, **_kwargs: None,
        sleep=lambda _seconds: None,
        thread_factory=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
        append_chat_event=lambda job_id, event_type, payload: append_calls.append(
            {
                "job_id": str(job_id),
                "type": str(event_type),
                "status": str((payload or {}).get("status") or ""),
                "error": str((payload or {}).get("error") or ""),
            }
        )
        or {},
        stop_event=stop_event,
    )

    chat_job_worker_loop(deps=deps)

    assert write_calls == [
        {"job_id": "cjob_err_1", "status": "failed", "error": "chat_job_failed"}
    ]
    assert append_calls == [
        {
            "job_id": "cjob_err_1",
            "type": "job.failed",
            "status": "failed",
            "error": "chat_job_failed",
        }
    ]
