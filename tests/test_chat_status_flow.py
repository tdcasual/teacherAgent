from __future__ import annotations

import threading
import unittest

from services.api.chat_status_service import ChatStatusDeps, get_chat_status


class ChatStatusServiceTest(unittest.TestCase):
    def test_get_chat_status_enqueues_pending_job_and_updates_lane_metrics(self):
        enqueue_calls = []
        lock = threading.Lock()

        deps = ChatStatusDeps(
            load_chat_job=lambda job_id: {"job_id": job_id, "status": "queued", "lane_id": "lane:teacher:main"},
            enqueue_chat_job=lambda job_id, lane_id: enqueue_calls.append((job_id, lane_id)) or {},
            resolve_chat_lane_id_from_job=lambda job: "lane:fallback",
            chat_job_lock=lock,
            chat_lane_load_locked=lambda lane_id: {"queued": 3, "active": 1, "total": 4},
            chat_find_position_locked=lambda lane_id, job_id: 2,
        )

        result = get_chat_status("cjob_001", deps=deps)
        self.assertEqual(result["lane_queue_position"], 2)
        self.assertEqual(result["lane_queue_size"], 3)
        self.assertTrue(result["lane_active"])
        self.assertEqual(enqueue_calls, [("cjob_001", "lane:teacher:main")])

    def test_get_chat_status_raises_when_job_missing(self):
        deps = ChatStatusDeps(
            load_chat_job=lambda job_id: (_ for _ in ()).throw(FileNotFoundError(job_id)),
            enqueue_chat_job=lambda job_id, lane_id: {},
            resolve_chat_lane_id_from_job=lambda job: "lane:fallback",
            chat_job_lock=threading.Lock(),
            chat_lane_load_locked=lambda lane_id: {"queued": 0, "active": 0, "total": 0},
            chat_find_position_locked=lambda lane_id, job_id: 0,
        )

        with self.assertRaises(FileNotFoundError):
            get_chat_status("missing", deps=deps)


if __name__ == "__main__":
    unittest.main()
