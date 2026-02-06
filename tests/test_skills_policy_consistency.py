import unittest
from pathlib import Path


class SkillsPolicyConsistencyTest(unittest.TestCase):
    def test_skill_tool_policy_matches_roles(self):
        from services.api.app import APP_ROOT, allowed_tools
        from services.api.skills.loader import load_skills

        loaded = load_skills(Path(APP_ROOT) / "skills")
        role_allowed = {
            "teacher": set(allowed_tools("teacher")),
            "student": set(allowed_tools("student")),
        }

        for skill_id, spec in loaded.skills.items():
            allow = spec.agent.tools.allow or []
            deny = spec.agent.tools.deny or []
            referenced = set(allow) | set(deny)
            if not referenced:
                continue
            # At least one of the skill's roles must be able to call referenced tools.
            ok = False
            for role in spec.allowed_roles or []:
                if referenced.issubset(role_allowed.get(role, set())):
                    ok = True
                    break
            self.assertTrue(ok, f"{skill_id}: tool policy not compatible with allowed_roles")

    def test_skill_budgets_are_positive(self):
        from services.api.app import APP_ROOT
        from services.api.skills.loader import load_skills

        loaded = load_skills(Path(APP_ROOT) / "skills")
        for skill_id, spec in loaded.skills.items():
            b = spec.agent.budgets
            if b.max_tool_calls is not None:
                self.assertGreaterEqual(b.max_tool_calls, 1, f"{skill_id}: max_tool_calls must be >= 1")
            if b.max_tool_rounds is not None:
                self.assertGreaterEqual(b.max_tool_rounds, 1, f"{skill_id}: max_tool_rounds must be >= 1")


if __name__ == "__main__":
    unittest.main()

