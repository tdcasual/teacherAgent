from __future__ import annotations

import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.chat_worker_service import ChatWorkerDeps, enqueue_chat_job, start_chat_worker


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


if __name__ == "__main__":
    unittest.main()
