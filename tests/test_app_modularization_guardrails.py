import importlib
import unittest


class AppModularizationGuardrailsTest(unittest.TestCase):
    def test_app_has_domain_deps_factories(self):
        import services.api.app as app_mod

        importlib.reload(app_mod)
        self.assertTrue(hasattr(app_mod, "_exam_api_deps"))
        self.assertTrue(hasattr(app_mod, "_assignment_api_deps"))


if __name__ == "__main__":
    unittest.main()
