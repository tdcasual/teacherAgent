import unittest


class TestPromptBuilder(unittest.TestCase):
    def test_teacher_prompt_compiles(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, modules = compile_system_prompt("teacher", version="v1", debug=False)
        self.assertTrue(prompt.strip())
        self.assertIn("安全规则", prompt)
        self.assertIn("作业流程", prompt)
        self.assertIn("exam.list", prompt)
        self.assertTrue(any("teacher/10_role.md" in m for m in modules))

    def test_student_prompt_compiles(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, modules = compile_system_prompt("student", version="v1", debug=False)
        self.assertTrue(prompt.strip())
        self.assertIn("学生端物理学习助手", prompt)
        self.assertIn("LaTeX", prompt)
        self.assertTrue(any("student/10_role.md" in m for m in modules))

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


if __name__ == "__main__":
    unittest.main()
