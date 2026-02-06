import unittest
from pathlib import Path


class SkillsFirstClassTest(unittest.TestCase):
    def test_skill_loader_and_tool_policy(self):
        from services.api.app import APP_ROOT, allowed_tools
        from services.api.skills.loader import load_skills
        from services.api.skills.runtime import compile_skill_runtime

        loaded = load_skills(Path(APP_ROOT) / "skills")
        self.assertIn("physics-core-examples", loaded.skills)
        self.assertIn("physics-teacher-ops", loaded.skills)

        role_allowed = set(allowed_tools("teacher"))

        core = loaded.skills["physics-core-examples"]
        core_rt = compile_skill_runtime(core)
        self.assertEqual(core_rt.max_tool_calls, 10)
        self.assertEqual(core_rt.max_tool_rounds, 4)
        filtered = core_rt.apply_tool_policy(role_allowed)
        self.assertEqual(
            filtered,
            {"core_example.search", "core_example.register", "core_example.render"},
        )
        self.assertIn("激活技能：physics-core-examples", core_rt.system_prompt)
        self.assertIn("核心例题库", core_rt.system_prompt)

        teacher_ops = loaded.skills["physics-teacher-ops"]
        ops_rt = compile_skill_runtime(teacher_ops)
        filtered_ops = ops_rt.apply_tool_policy(role_allowed)
        denied = {
            "teacher.llm_routing.get",
            "teacher.llm_routing.simulate",
            "teacher.llm_routing.propose",
            "teacher.llm_routing.apply",
            "teacher.llm_routing.rollback",
        }
        self.assertEqual(filtered_ops, role_allowed - denied)

    def test_router_fallback_and_role_gate(self):
        from services.api.app import APP_ROOT
        from services.api.skills.loader import load_skills
        from services.api.skills.router import resolve_skill

        loaded = load_skills(Path(APP_ROOT) / "skills")

        sel = resolve_skill(loaded, requested_skill_id="!!!", role_hint="teacher")
        self.assertIsNotNone(sel.skill)
        self.assertEqual(sel.skill.skill_id, "physics-teacher-ops")

        # Student cannot select teacher-only skills; should fall back to student default.
        sel2 = resolve_skill(loaded, requested_skill_id="physics-core-examples", role_hint="student")
        self.assertIsNotNone(sel2.skill)
        self.assertEqual(sel2.skill.skill_id, "physics-student-coach")


if __name__ == "__main__":
    unittest.main()
