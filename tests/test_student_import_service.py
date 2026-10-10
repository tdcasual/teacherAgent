import unittest

from services.api.student_import_service import student_import


class StudentImportServiceTest(unittest.TestCase):
    def test_student_import_is_gone(self):
        result = student_import({}, deps=None)  # type: ignore[arg-type]
        self.assertEqual(result.get("error"), "gone")
        self.assertEqual(result.get("status_code"), 410)


if __name__ == "__main__":
    unittest.main()
