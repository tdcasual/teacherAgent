from pathlib import Path
import unittest

from services.api.assignment_intent_service import detect_assignment_intent
from services.api.skill_auto_router import resolve_effective_skill


APP_ROOT = Path(__file__).resolve().parents[1]


class SkillAutoRouterTest(unittest.TestCase):
    def test_explicit_skill_is_preserved(self):
        result = resolve_effective_skill(
            app_root=APP_ROOT,
            role_hint="teacher",
            requested_skill_id="physics-core-examples",
            last_user_text="登记核心例题 CE001",
            detect_assignment_intent=detect_assignment_intent,
        )
        self.assertEqual(result.get("effective_skill_id"), "physics-core-examples")
        self.assertEqual(result.get("reason"), "explicit")

    def test_teacher_auto_routes_assignment_to_homework_skill(self):
        result = resolve_effective_skill(
            app_root=APP_ROOT,
            role_hint="teacher",
            requested_skill_id="",
            last_user_text="请帮我生成作业，作业ID A2403_2026-02-04，每个知识点 5 题",
            detect_assignment_intent=detect_assignment_intent,
        )
        self.assertEqual(result.get("effective_skill_id"), "physics-homework-generator")
        self.assertIn("auto_rule", str(result.get("reason") or ""))

    def test_teacher_auto_routes_llm_routing_requests(self):
        result = resolve_effective_skill(
            app_root=APP_ROOT,
            role_hint="teacher",
            requested_skill_id=None,
            last_user_text="先读取当前模型路由配置，再回滚到版本 3",
            detect_assignment_intent=detect_assignment_intent,
        )
        self.assertEqual(result.get("effective_skill_id"), "physics-llm-routing")
        self.assertIn("auto_rule", str(result.get("reason") or ""))

    def test_ambiguous_low_margin_falls_back_to_default(self):
        result = resolve_effective_skill(
            app_root=APP_ROOT,
            role_hint="teacher",
            requested_skill_id="",
            last_user_text="我想要一个分析方案",
            detect_assignment_intent=detect_assignment_intent,
        )
        self.assertTrue(str(result.get("reason") or "").startswith("role_default") or "default" in str(result.get("reason") or ""))
        self.assertEqual(result.get("effective_skill_id"), "physics-teacher-ops")

    def test_student_invalid_requested_skill_falls_back_to_student_default(self):
        result = resolve_effective_skill(
            app_root=APP_ROOT,
            role_hint="student",
            requested_skill_id="physics-teacher-ops",
            last_user_text="开始今天作业",
            detect_assignment_intent=detect_assignment_intent,
        )
        self.assertEqual(result.get("effective_skill_id"), "physics-student-coach")


if __name__ == "__main__":
    unittest.main()
