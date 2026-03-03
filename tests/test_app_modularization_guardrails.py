import importlib
import unittest


class AppModularizationGuardrailsTest(unittest.TestCase):
    def test_app_has_domain_deps_factories(self):
        import services.api.app as app_mod

        importlib.reload(app_mod)
        core = app_mod.get_core()
        self.assertTrue(hasattr(core, "exam_upload_ops_deps"))
        self.assertTrue(hasattr(core, "assignment_handlers_deps"))

    def test_app_module_imports_are_thin(self):
        import services.api.app as app_mod

        importlib.reload(app_mod)
        self.assertIsNotNone(app_mod)
        core = app_mod.get_core()
        for name in (
            "exam_upload_ops_deps",
            "assignment_handlers_deps",
            "student_import_deps",
            "teacher_model_config_deps",
            "chat_start",
            "chat_status",
            "chat_event_stream_deps",
            "chart_exec",
            "teacher_memory_list_proposals",
        ):
            self.assertTrue(hasattr(core, name))
            self.assertFalse(hasattr(app_mod, name))


if __name__ == "__main__":
    unittest.main()
