from pathlib import Path
import unittest

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
        self.assertIn("assignment_generate", list(getattr(routing, "intents", []) or []))

    def test_routing_thresholds_have_safe_defaults(self):
        loaded = load_skills(APP_ROOT / "skills")
        spec = loaded.skills["physics-teacher-ops"]
        routing = getattr(spec, "routing", None)
        self.assertIsNotNone(routing)
        self.assertGreaterEqual(int(getattr(routing, "min_score", 0)), 1)
        self.assertGreaterEqual(int(getattr(routing, "min_margin", -1)), 0)
        self.assertGreaterEqual(float(getattr(routing, "confidence_floor", -1.0)), 0.0)


if __name__ == "__main__":
    unittest.main()
