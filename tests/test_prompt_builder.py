import unittest


class TestPromptBuilder(unittest.TestCase):
    def test_teacher_prompt_compiles(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, modules = compile_system_prompt("teacher", version="v1", debug=False)
        self.assertTrue(prompt.strip())
        self.assertIn("安全规则", prompt)
        self.assertIn("作业流程", prompt)
        self.assertNotIn("exam.list", prompt)
        self.assertIn("assignment.list", prompt)
        self.assertTrue(any("teacher/10_role.md" in m for m in modules))

    def test_student_prompt_compiles(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, modules = compile_system_prompt("student", version="v1", debug=False)
        self.assertTrue(prompt.strip())
        self.assertIn("学生端学习助手", prompt)
        self.assertNotIn("物理学习助手", prompt)
        self.assertNotIn("物理教学助手", prompt)
        self.assertNotIn("列出考试", prompt)
        self.assertIn("LaTeX", prompt)
        self.assertTrue(any("student/10_role.md" in m for m in modules))

    def test_role_prompts_drop_physics_product_identity(self):
        from services.api.prompt_builder import compile_system_prompt

        teacher, _ = compile_system_prompt("teacher", version="v1", debug=False)
        student, _ = compile_system_prompt("student", version="v1", debug=False)
        self.assertIn("教学助手", teacher)
        self.assertNotIn("物理教学助手", teacher)
        self.assertNotIn("列出考试", teacher)
        self.assertIn("学生端学习助手", student)
        self.assertNotIn("物理学习助手", student)
        self.assertNotIn("列出考试", student)
        self.assertNotIn("生成作业", student)

    def test_generic_overlay_does_not_fight_student_base_identity(self):
        from services.api.prompt_builder import compile_system_prompt
        from services.api.subject_pack_service import student_prompt_overlay

        overlay = student_prompt_overlay("generic")
        prompt, modules = compile_system_prompt(
            "student", version="v1", debug=False, overlay=overlay
        )
        self.assertIn("学生端学习助手", prompt)
        self.assertIn("【学科 overlay：通用】", prompt)
        self.assertIn("subject_overlay", modules)
        self.assertNotIn("物理学习助手", prompt)
        self.assertNotIn("物理教学助手", prompt)

    def test_unknown_prompt_compiles(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, modules = compile_system_prompt(None, version="v1", debug=False)
        self.assertTrue(prompt.strip())
        self.assertIn("当前身份未知", prompt)
        self.assertTrue(any("common/10_role_detect.md" in m for m in modules))

    def test_debug_prompt_contains_module_markers(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, _ = compile_system_prompt("teacher", version="v1", debug=True)
        self.assertIn("【MODULE:", prompt)
        prompt2, _ = compile_system_prompt("teacher", version="v1", debug=False)
        self.assertNotIn("【MODULE:", prompt2)

    def test_role_resolution_unknown(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, _ = compile_system_prompt("nonsense", version="v1", debug=False)
        self.assertIn("当前身份未知", prompt)

    def test_compiled_prompt_has_trailing_newline(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, _ = compile_system_prompt("teacher", version="v1", debug=False)
        self.assertTrue(prompt.endswith("\n"))

    def test_optional_overlay_is_appended(self):
        from services.api.prompt_builder import compile_system_prompt

        overlay = "【学科 overlay：通用】中性陪练，无学科公式包。"
        prompt, modules = compile_system_prompt(
            "student", version="v1", debug=False, overlay=overlay
        )
        self.assertIn(overlay, prompt)
        self.assertIn("subject_overlay", modules)
        self.assertTrue(prompt.endswith("\n"))

        base, base_modules = compile_system_prompt("student", version="v1", debug=False)
        self.assertNotIn(overlay, base)
        self.assertNotIn("subject_overlay", base_modules)

    def test_optional_overlay_blank_is_ignored(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, modules = compile_system_prompt(
            "student", version="v1", debug=False, overlay="  \n"
        )
        self.assertNotIn("subject_overlay", modules)
        self.assertTrue(prompt.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
