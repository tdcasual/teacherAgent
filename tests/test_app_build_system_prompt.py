import unittest


class TestAppBuildSystemPrompt(unittest.TestCase):
    def test_build_system_prompt_teacher(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, _modules = compile_system_prompt("teacher", version="v1", debug=False)
        self.assertIn("教学助手", prompt)
        self.assertNotIn("exam.list", prompt)
        self.assertIn("assignment.list", prompt)

    def test_build_system_prompt_student(self):
        from services.api.prompt_builder import compile_system_prompt

        prompt, _modules = compile_system_prompt("student", version="v1", debug=False)
        self.assertIn("学生端物理学习助手", prompt)
        self.assertIn("LaTeX", prompt)


if __name__ == "__main__":
    unittest.main()
