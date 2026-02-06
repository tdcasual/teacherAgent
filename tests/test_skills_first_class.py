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
            {"core_example.search", "core_example.register", "core_example.render", "chart.agent.run", "chart.exec"},
        )
        self.assertIn("激活技能：physics-core-examples", core_rt.system_prompt)
        self.assertIn("核心例题库", core_rt.system_prompt)
        core_model_targets = core_rt.resolve_model_targets(
            role_hint="teacher",
            kind="chat.agent_no_tools",
            needs_tools=False,
            needs_json=False,
        )
        self.assertTrue(core_model_targets)
        self.assertEqual((core_model_targets[0] or {}).get("route_id"), "core_summary")

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
        ops_longform_targets = ops_rt.resolve_model_targets(
            role_hint="teacher",
            kind="chat.exam_longform",
            needs_tools=False,
            needs_json=False,
        )
        self.assertTrue(ops_longform_targets)
        self.assertEqual((ops_longform_targets[0] or {}).get("route_id"), "exam_longform")

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

    def test_chart_exec_policy_teacher_yes_student_no(self):
        from services.api.app import APP_ROOT, allowed_tools
        from services.api.skills.loader import load_skills
        from services.api.skills.runtime import compile_skill_runtime

        loaded = load_skills(Path(APP_ROOT) / "skills")
        teacher_allowed = set(allowed_tools("teacher"))
        student_allowed = set(allowed_tools("student"))

        self.assertIn("chart.exec", teacher_allowed)
        self.assertIn("chart.agent.run", teacher_allowed)
        self.assertNotIn("chart.exec", student_allowed)
        self.assertNotIn("chart.agent.run", student_allowed)

        for skill_id, spec in loaded.skills.items():
            runtime = compile_skill_runtime(spec)
            if "teacher" in (spec.allowed_roles or []):
                filtered_teacher = runtime.apply_tool_policy(teacher_allowed)
                self.assertIn("chart.exec", filtered_teacher, f"{skill_id}: teacher should be able to use chart.exec")
                self.assertIn("chart.agent.run", filtered_teacher, f"{skill_id}: teacher should be able to use chart.agent.run")
            if "student" in (spec.allowed_roles or []):
                filtered_student = runtime.apply_tool_policy(student_allowed)
                self.assertNotIn("chart.exec", filtered_student, f"{skill_id}: student must not use chart.exec")
                self.assertNotIn("chart.agent.run", filtered_student, f"{skill_id}: student must not use chart.agent.run")

    def test_model_policy_can_distinguish_roles(self):
        from services.api.app import APP_ROOT
        from services.api.skills.loader import load_skills
        from services.api.skills.runtime import compile_skill_runtime

        loaded = load_skills(Path(APP_ROOT) / "skills")
        coach_rt = compile_skill_runtime(loaded.skills["physics-student-coach"])

        teacher_targets = coach_rt.resolve_model_targets(
            role_hint="teacher",
            kind="chat.agent",
            needs_tools=True,
            needs_json=False,
        )
        student_targets = coach_rt.resolve_model_targets(
            role_hint="student",
            kind="chat.agent",
            needs_tools=False,
            needs_json=False,
        )

        self.assertTrue(teacher_targets)
        self.assertTrue(student_targets)
        self.assertEqual((teacher_targets[0] or {}).get("route_id"), "teacher_diagnosis")
        self.assertEqual((student_targets[0] or {}).get("route_id"), "student_dialogue")


if __name__ == "__main__":
    unittest.main()
