from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from services.api.teacher_memory_insights_service import TeacherMemoryInsightsDeps, teacher_memory_insights


class TeacherMemoryInsightsServiceTest(unittest.TestCase):
    def test_teacher_memory_insights_aggregates_proposals_and_events(self):
        now = datetime.now()
        proposals = [
            {
                "proposal_id": "p1",
                "status": "applied",
                "target": "MEMORY",
                "source": "manual",
                "title": "t1",
                "content": "c1",
                "created_at": (now - timedelta(days=1)).isoformat(timespec="seconds"),
            },
            {
                "proposal_id": "p2",
                "status": "rejected",
                "target": "DAILY",
                "source": "auto_intent",
                "title": "t2",
                "content": "c2",
                "reject_reason": "duplicate",
                "created_at": (now - timedelta(days=1)).isoformat(timespec="seconds"),
            },
        ]
        events = [
            {"ts": (now - timedelta(days=1)).isoformat(timespec="seconds"), "event": "search", "mode": "mem0", "query": "q1", "hits": 1},
            {"ts": (now - timedelta(days=1)).isoformat(timespec="seconds"), "event": "context_injected"},
        ]

        deps = TeacherMemoryInsightsDeps(
            ensure_teacher_workspace=lambda teacher_id: None,
            recent_proposals=lambda teacher_id, limit: proposals,
            is_expired_record=lambda rec, now: False,
            priority_score=lambda **kwargs: 60,
            rank_score=lambda rec: 60.0,
            age_days=lambda rec, now: 1,
            load_events=lambda teacher_id, limit: events,
            parse_dt=lambda value: datetime.fromisoformat(str(value)),
        )

        result = teacher_memory_insights("teacher_1", deps=deps, days=14)
        self.assertTrue(result.get("ok"))
        summary = result.get("summary") or {}
        retrieval = result.get("retrieval") or {}
        self.assertEqual(summary.get("applied_total"), 1)
        self.assertEqual(summary.get("rejected_total"), 1)
        self.assertEqual(retrieval.get("search_calls"), 1)
        self.assertEqual(retrieval.get("context_injected"), 1)


if __name__ == "__main__":
    unittest.main()
