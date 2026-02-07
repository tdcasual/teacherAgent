from __future__ import annotations

import re
import unittest
from datetime import datetime, timedelta

from services.api.teacher_memory_rules_service import (
    teacher_memory_conflicts,
    teacher_memory_is_expired_record,
    teacher_memory_norm_text,
    teacher_memory_priority_score,
    teacher_memory_record_expire_at,
    teacher_memory_record_ttl_days,
)


class TeacherMemoryRulesServiceTest(unittest.TestCase):
    def test_record_ttl_uses_target_fallback(self):
        rec = {"target": "DAILY", "source": "auto_flush"}
        ttl = teacher_memory_record_ttl_days(rec, ttl_days_daily=2, ttl_days_memory=30)
        self.assertEqual(ttl, 2)

    def test_expiration_and_decay_helpers(self):
        rec = {"created_at": (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds"), "ttl_days": 1}
        expire_at = teacher_memory_record_expire_at(
            rec,
            parse_dt=lambda raw: datetime.fromisoformat(str(raw)) if raw else None,
            record_ttl_days=lambda _: 1,
        )
        self.assertIsNotNone(expire_at)
        expired = teacher_memory_is_expired_record(
            rec,
            decay_enabled=True,
            record_expire_at=lambda _: expire_at,
            now=datetime.now(),
        )
        self.assertTrue(expired)

    def test_priority_and_conflict_detection(self):
        score = teacher_memory_priority_score(
            target="MEMORY",
            title="偏好",
            content="请记住以后输出采用固定格式",
            source="manual",
            meta={"similar_hits": 2},
            durable_intent_patterns=[re.compile(r"记住")],
            auto_infer_stable_patterns=[re.compile(r"以后")],
            temporary_hint_patterns=[re.compile(r"今天")],
            is_sensitive=lambda text: False,
            norm_text=teacher_memory_norm_text,
        )
        self.assertGreaterEqual(score, 70)

        has_conflict = teacher_memory_conflicts(
            "答案要简洁",
            "答案要详细",
            norm_text=teacher_memory_norm_text,
            conflict_groups=[(("简洁",), ("详细",))],
        )
        self.assertTrue(has_conflict)


if __name__ == "__main__":
    unittest.main()
