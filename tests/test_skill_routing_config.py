from pathlib import Path
import unittest

from services.api.assignment_intent_service import detect_assignment_intent
from services.api.skill_auto_router import resolve_effective_skill
from services.api.skills.loader import load_skills


APP_ROOT = Path(__file__).resolve().parents[1]


class SkillRoutingConfigTest(unittest.TestCase):
    def test_skill_spec_exposes_routing_config(self):
        loaded = load_skills(APP_ROOT / "skills")
        self.assertIn("physics-homework-generator", loaded.skills)
        spec = loaded.skills["physics-homework-generator"]
        routing = getattr(spec, "routing", None)
        self.assertIsNotNone(routing)
        self.assertIn("生成作业", list(getattr(routing, "keywords", []) or []))

    def test_auto_router_uses_skill_yaml_routing_keywords(self):
        # This query intentionally avoids explicit "学生/同学" wording.
        # With rule-only routing it tends to fall back to teacher-ops;
        # with skill.yaml routing keywords it should match student-focus.
        result = resolve_effective_skill(
            app_root=APP_ROOT,
            role_hint="teacher",
            requested_skill_id="",
            last_user_text="请给我画像更新建议，聚焦最近一次练习",
            detect_assignment_intent=detect_assignment_intent,
        )
        self.assertEqual(result.get("effective_skill_id"), "physics-student-focus")


if __name__ == "__main__":
    unittest.main()
