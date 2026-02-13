from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import grade_submission as gs


class GradeSubmissionSecurityTest(unittest.TestCase):
    def test_require_safe_id_accepts_expected_tokens(self):
        self.assertEqual(gs.require_safe_id("S1", "student_id"), "S1")
        self.assertEqual(gs.require_safe_id("HW_2026-02-13", "assignment_id"), "HW_2026-02-13")

    def test_require_safe_id_rejects_path_traversal_tokens(self):
        with self.assertRaises(SystemExit):
            gs.require_safe_id("../escape", "student_id")
        with self.assertRaises(SystemExit):
            gs.require_safe_id("A/../../x", "assignment_id")

    def test_resolve_under_blocks_escape_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            safe = gs.resolve_under(root, "student", "submission_1")
            self.assertTrue(safe == (root / "student" / "submission_1").resolve())
            with self.assertRaises(SystemExit):
                gs.resolve_under(root, "..", "escape")


if __name__ == "__main__":
    unittest.main()
