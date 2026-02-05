import unittest


class TestAppBuildSystemPrompt(unittest.TestCase):
    def test_build_system_prompt_teacher(self):
        from services.api.app import build_system_prompt

        prompt = build_system_prompt("teacher")
        self.assertIn("物理教学助手", prompt)
        self.assertIn("exam.list", prompt)

    def test_build_system_prompt_student(self):
        from services.api.app import build_system_prompt

        prompt = build_system_prompt("student")
        self.assertIn("学生端物理学习助手", prompt)
        self.assertIn("LaTeX", prompt)


if __name__ == "__main__":
    unittest.main()

