import unittest
from pathlib import Path


class SkillsFirstClassTest(unittest.TestCase):
    def test_skill_loader_and_tool_policy(self):
        from services.api.config import APP_ROOT
        from services.api.core_services import allowed_tools
        from services.api.skills.loader import load_skills
        from services.api.skills.runtime import compile_skill_runtime

        loaded = load_skills(Path(APP_ROOT) / "skills")
        self.assertIn("physics-core-examples", loaded.skills)
        self.assertIn("teacher-assignment-ops", loaded.skills)

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

        teacher_ops = loaded.skills["teacher-assignment-ops"]
        ops_rt = compile_skill_runtime(teacher_ops)
        filtered_ops = ops_rt.apply_tool_policy(role_allowed)
        self.assertIn("assignment.progress", filtered_ops)
        self.assertIn("assignment.missing", filtered_ops)
        self.assertNotIn("assignment.generate", filtered_ops)
        self.assertNotIn("exam.get", filtered_ops)
        self.assertIn("chart.exec", filtered_ops)
        ops_planning_targets = ops_rt.resolve_model_targets(
            role_hint="teacher",
            kind="chat.agent_no_tools",
            needs_tools=False,
            needs_json=False,
        )
        self.assertTrue(ops_planning_targets)
        self.assertEqual((ops_planning_targets[0] or {}).get("route_id"), "planning_no_tools")

    def test_router_fallback_and_role_gate(self):
        from services.api.config import APP_ROOT
        from services.api.skills.loader import load_skills
        from services.api.skills.router import resolve_skill

        loaded = load_skills(Path(APP_ROOT) / "skills")

        sel = resolve_skill(loaded, requested_skill_id="!!!", role_hint="teacher")
        self.assertIsNotNone(sel.skill)
        self.assertEqual(sel.skill.skill_id, "teacher-assignment-ops")

        # Student cannot select teacher-only skills; should fall back to student default.
        sel2 = resolve_skill(loaded, requested_skill_id="physics-core-examples", role_hint="student")
        self.assertIsNotNone(sel2.skill)
        self.assertEqual(sel2.skill.skill_id, "student-coach")

        aliased = resolve_skill(loaded, requested_skill_id="physics-teacher-ops", role_hint="teacher")
        self.assertIsNotNone(aliased.skill)
        self.assertEqual(aliased.skill.skill_id, "teacher-assignment-ops")
        self.assertEqual(aliased.warning, "skill_id_aliased")

        aliased_hw = resolve_skill(loaded, requested_skill_id="physics-homework-generator", role_hint="teacher")
        self.assertIsNotNone(aliased_hw.skill)
        self.assertEqual(aliased_hw.skill.skill_id, "homework-generator")
        self.assertEqual(aliased_hw.warning, "skill_id_aliased")

    def test_remaining_physics_skill_ids_are_pack_affiliates_not_defaults(self):
        from services.api.config import APP_ROOT
        from services.api.skills.loader import load_skills
        from services.api.skills.router import default_skill_id_for_role
        from services.api.subject_pack_service import load_pack

        loaded = load_skills(Path(APP_ROOT) / "skills")
        physics_ids = {skill_id for skill_id in loaded.skills if skill_id.startswith("physics-")}
        affiliates = set(load_pack("physics").skill_affiliates)
        self.assertEqual(
            physics_ids,
            {
                "physics-lesson-capture",
                "physics-core-examples",
                "physics-student-focus",
            },
        )
        self.assertEqual(physics_ids, affiliates)
        self.assertNotIn(default_skill_id_for_role("teacher"), physics_ids)
        self.assertNotIn(default_skill_id_for_role("student"), physics_ids)
        self.assertTrue((Path(APP_ROOT) / "skills" / "physics-lesson-capture" / "skill.yaml").is_file())
        self.assertTrue((Path(APP_ROOT) / "skills" / "physics-core-examples" / "skill.yaml").is_file())

    def test_chart_exec_policy_teacher_yes_student_no(self):
        from services.api.config import APP_ROOT
        from services.api.core_services import allowed_tools
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
        from services.api.config import APP_ROOT
        from services.api.skills.loader import load_skills
        from services.api.skills.runtime import compile_skill_runtime

        loaded = load_skills(Path(APP_ROOT) / "skills")
        coach_rt = compile_skill_runtime(loaded.skills["student-coach"])

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
