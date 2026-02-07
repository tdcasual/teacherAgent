import importlib
import unittest


class AppModularizationGuardrailsTest(unittest.TestCase):
    def test_app_has_domain_deps_factories(self):
        import services.api.app as app_mod

        importlib.reload(app_mod)
        self.assertTrue(hasattr(app_mod, "_exam_api_deps"))
        self.assertTrue(hasattr(app_mod, "_assignment_api_deps"))

    def test_app_module_imports_are_thin(self):
        import services.api.app as app_mod

        importlib.reload(app_mod)
        self.assertIsNotNone(app_mod)
        for name in (
            "_exam_api_deps",
            "_assignment_api_deps",
            "_student_profile_api_deps",
            "_teacher_routing_api_deps",
            "_chart_api_deps",
            "_chat_api_deps",
            "_teacher_memory_api_deps",
        ):
            self.assertTrue(hasattr(app_mod, name))


if __name__ == "__main__":
    unittest.main()
