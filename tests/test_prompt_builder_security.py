import importlib
import os
import unittest


class TestPromptBuilderSecurity(unittest.TestCase):
    def test_path_traversal_rejected(self):
        from services.api import prompt_builder

        # _read_module is internal but we want to ensure traversal is blocked.
        with self.assertRaises(Exception):
            prompt_builder._read_module("v1", "../README.md")  # type: ignore[attr-defined]

    def test_missing_manifest_raises(self):
        from services.api.prompt_builder import compile_system_prompt

        with self.assertRaises(Exception):
            compile_system_prompt("teacher", version="does_not_exist", debug=False)

    def test_env_version_default_used_on_reload(self):
        # Ensure DEFAULT_PROMPT_VERSION is read from env at import time.
        os.environ["PROMPT_VERSION"] = "v1"
        mod = importlib.import_module("services.api.prompt_builder")
        importlib.reload(mod)
        prompt, _ = mod.compile_system_prompt("student", version=None, debug=False)
        self.assertIn("学生端物理学习助手", prompt)


if __name__ == "__main__":
    unittest.main()

