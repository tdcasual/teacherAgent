import unittest


class SkillPromptModuleSecurityTest(unittest.TestCase):
    def test_prompt_module_path_traversal_blocked(self):
        from services.api.skills.runtime import compile_skill_runtime
        from services.api.skills.spec import (
            SkillAgentSpec,
            SkillBudgets,
            SkillModelPolicy,
            SkillSpec,
            SkillToolsPolicy,
            SkillUiSpec,
        )

        spec = SkillSpec(
            skill_id="test-skill",
            schema_version=2,
            title="Test",
            desc="",
            allowed_roles=["teacher"],
            ui=SkillUiSpec(prompts=[], examples=[]),
            agent=SkillAgentSpec(
                prompt_modules=["../../../../etc/passwd"],
                context_providers=[],
                tools=SkillToolsPolicy(allow=None, deny=[]),
                budgets=SkillBudgets(max_tool_rounds=None, max_tool_calls=None),
                model_policy=SkillModelPolicy(enabled=False, default=None, routes=[]),
            ),
            source_path="(in-memory)",
        )

        with self.assertRaises(ValueError):
            compile_skill_runtime(spec)

    def test_prompt_module_can_load_valid_file(self):
        from services.api.skills.runtime import compile_skill_runtime
        from services.api.skills.spec import (
            SkillAgentSpec,
            SkillBudgets,
            SkillModelPolicy,
            SkillSpec,
            SkillToolsPolicy,
            SkillUiSpec,
        )

        spec = SkillSpec(
            skill_id="test-skill-valid",
            schema_version=2,
            title="TestValid",
            desc="",
            allowed_roles=["teacher"],
            ui=SkillUiSpec(prompts=[], examples=[]),
            agent=SkillAgentSpec(
                prompt_modules=["teacher/skills/core_examples.md"],
                context_providers=[],
                tools=SkillToolsPolicy(allow=None, deny=[]),
                budgets=SkillBudgets(max_tool_rounds=None, max_tool_calls=None),
                model_policy=SkillModelPolicy(enabled=False, default=None, routes=[]),
            ),
            source_path="(in-memory)",
        )

        runtime = compile_skill_runtime(spec)
        self.assertIn("激活技能：test-skill-valid", runtime.system_prompt)
        self.assertIn("核心例题库", runtime.system_prompt)


if __name__ == "__main__":
    unittest.main()
