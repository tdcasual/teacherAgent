import unittest
from collections import deque

from services.api.chat_queue_service import (
    chat_enqueue,
    chat_find_position,
    chat_has_pending,
    chat_lane_load,
    chat_mark_done,
    chat_pick_next,
    chat_recent_job,
    chat_register_recent,
)


class ChatQueueServiceTest(unittest.TestCase):
    def test_chat_enqueue_is_idempotent_and_tracks_position(self):
        lanes = {}
        queued = set()
        job_to_lane = {}

        pos_1 = chat_enqueue(lanes, queued, job_to_lane, "job_1", "lane_a")
        pos_2 = chat_enqueue(lanes, queued, job_to_lane, "job_1", "lane_a")
        pos_3 = chat_enqueue(lanes, queued, job_to_lane, "job_2", "lane_a")

        self.assertEqual(pos_1, 1)
        self.assertEqual(pos_2, 1)
        self.assertEqual(pos_3, 2)
        self.assertEqual(chat_find_position(lanes, "lane_a", "job_1"), 1)
        self.assertEqual(chat_find_position(lanes, "lane_a", "job_2"), 2)

    def test_chat_pick_next_round_robin_skips_active_lane(self):
        lanes = {"lane_a": deque(["a1", "a2"]), "lane_b": deque(["b1"])}
        queued = {"a1", "a2", "b1"}
        active_lanes = set()
        job_to_lane = {"a1": "lane_a", "a2": "lane_a", "b1": "lane_b"}

        job_1, lane_1, cursor = chat_pick_next(lanes, active_lanes, queued, job_to_lane, lane_cursor=0)
        self.assertEqual((job_1, lane_1), ("a1", "lane_a"))

        job_2, lane_2, cursor = chat_pick_next(lanes, active_lanes, queued, job_to_lane, lane_cursor=cursor)
        self.assertEqual((job_2, lane_2), ("b1", "lane_b"))

        chat_mark_done(lanes, active_lanes, job_to_lane, "a1", "lane_a")
        chat_mark_done(lanes, active_lanes, job_to_lane, "b1", "lane_b")

        job_3, lane_3, cursor = chat_pick_next(lanes, active_lanes, queued, job_to_lane, lane_cursor=cursor)
        self.assertEqual((job_3, lane_3), ("a2", "lane_a"))

    def test_chat_lane_load_and_pending(self):
        lanes = {"lane_a": deque(["a1"]), "lane_b": deque([])}
        active_lanes = {"lane_b"}
        self.assertEqual(chat_lane_load(lanes, active_lanes, "lane_a"), {"queued": 1, "active": 0, "total": 1})
        self.assertEqual(chat_lane_load(lanes, active_lanes, "lane_b"), {"queued": 0, "active": 1, "total": 1})
        self.assertTrue(chat_has_pending(lanes))

    def test_chat_recent_job_honors_fingerprint_and_window(self):
        lane_recent = {}
        chat_register_recent(lane_recent, "lane_a", "fp_1", "job_1", now_ts=1000.0)

        self.assertEqual(chat_recent_job(lane_recent, "lane_a", "fp_1", debounce_ms=500, now_ts=1000.2), "job_1")
        self.assertIsNone(chat_recent_job(lane_recent, "lane_a", "fp_2", debounce_ms=500, now_ts=1000.2))
        self.assertIsNone(chat_recent_job(lane_recent, "lane_a", "fp_1", debounce_ms=500, now_ts=1000.6))


if __name__ == "__main__":
    unittest.main()
