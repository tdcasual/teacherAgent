import threading
import unittest
from pathlib import Path

from services.api.chat_state_store import (
    ChatIdempotencyStore,
    ChatStateStore,
    create_chat_idempotency_store,
    create_chat_state_store,
)


class ChatStateStoreTest(unittest.TestCase):
    def test_create_chat_state_store_defaults(self):
        state = create_chat_state_store()
        self.assertIsInstance(state, ChatStateStore)
        self.assertIsInstance(state.chat_job_lock, type(threading.Lock()))
        self.assertIsInstance(state.chat_job_event, type(threading.Event()))
        self.assertFalse(state.worker_started)
        self.assertEqual(state.lane_cursor, 0)
        self.assertEqual(state.chat_job_lanes, {})
        self.assertEqual(state.chat_job_active_lanes, set())
        self.assertEqual(state.chat_job_queued, set())
        self.assertEqual(state.chat_job_to_lane, {})
        self.assertEqual(state.chat_lane_recent, {})
        self.assertEqual(state.chat_worker_threads, [])

    def test_create_chat_idempotency_store_defaults(self):
        chat_job_dir = Path("/tmp/chat_jobs")
        store = create_chat_idempotency_store(chat_job_dir)
        self.assertIsInstance(store, ChatIdempotencyStore)
        self.assertEqual(store.request_map_dir, chat_job_dir / "request_index")
        self.assertEqual(store.request_index_path, chat_job_dir / "request_index.json")
        self.assertIsInstance(store.request_index_lock, type(threading.Lock()))

    def test_state_instances_are_isolated(self):
        left = create_chat_state_store()
        right = create_chat_state_store()
        left.chat_job_lanes["lane_a"] = None  # type: ignore[assignment]
        left.chat_job_active_lanes.add("lane_a")
        left.chat_job_queued.add("job_1")
        left.chat_job_to_lane["job_1"] = "lane_a"
        left.chat_lane_recent["lane_a"] = (1.0, "fp", "job_1")
        left.worker_started = True
        left.lane_cursor = 3
        self.assertNotEqual(left.chat_job_lanes, right.chat_job_lanes)
        self.assertNotEqual(left.chat_job_active_lanes, right.chat_job_active_lanes)
        self.assertNotEqual(left.chat_job_queued, right.chat_job_queued)
        self.assertNotEqual(left.chat_job_to_lane, right.chat_job_to_lane)
        self.assertNotEqual(left.chat_lane_recent, right.chat_lane_recent)
        self.assertNotEqual(left.worker_started, right.worker_started)
        self.assertNotEqual(left.lane_cursor, right.lane_cursor)


if __name__ == "__main__":
    unittest.main()
