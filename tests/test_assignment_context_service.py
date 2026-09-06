import unittest

from services.api.assignment_context_service import build_assignment_context


class AssignmentContextServiceTest(unittest.TestCase):
    def test_returns_none_when_detail_missing(self):
        self.assertIsNone(build_assignment_context(None))

    def test_non_study_mode_contains_data_block(self):
        detail = {
            "assignment_id": "A1",
            "date": "2026-02-07",
            "question_count": 5,
            "meta": {"mode": "upload", "target_kp": ["牛顿定律"]},
            "requirements": {},
        }
        result = build_assignment_context(detail, study_mode=False)
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("---BEGIN DATA---", result)
        self.assertIn("Assignment ID: A1", result)
        self.assertNotIn("【学习与诊断规则", result)

    def test_study_mode_does_not_require_discussion_marker(self):
        detail = {
            "assignment_id": "A1",
            "date": "2026-02-07",
            "question_count": 5,
            "meta": {"mode": "upload", "target_kp": ["牛顿定律"]},
            "requirements": {"subject": "物理", "topic": "力学"},
        }
        marker = "【个性化作业】"
        result = build_assignment_context(
            detail, study_mode=True, discussion_complete_marker=marker
        )
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("【学习与诊断规则", result)
        self.assertNotIn(marker, result)
        self.assertNotIn("K0)", result)
        self.assertNotIn("K) 个性化作业生成", result)
        self.assertIn("作业总要求", result)


if __name__ == "__main__":
    unittest.main()
