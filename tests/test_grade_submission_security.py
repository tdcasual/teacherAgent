import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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


    def test_attempt_dir_does_not_create_submission_trees(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            out_root = root / "student_submissions"
            practice = out_root / "HW_1" / "S1" / "practice_ab12cd"
            practice.mkdir(parents=True)
            questions = practice / "questions.csv"
            questions.write_text(
                "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
                "P1,力学,basic,open,,,,\n",
                encoding="utf-8",
            )
            upload = root / "page.png"
            upload.write_bytes(b"x")

            def fake_ocr(_files, out_dir, _language, _mode):
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "page_1.txt").write_text("答案：1", encoding="utf-8")
                return "答案：1"

            argv = [
                "grade_submission.py",
                "--student-id",
                "S1",
                "--assignment-id",
                "HW_1",
                "--out-dir",
                str(out_root),
                "--files",
                str(upload),
                "--attempt-dir",
                str(practice),
                "--skip-profile-update",
                "--assignment-questions",
                str(questions),
            ]
            with patch.object(gs, "ocr_files", fake_ocr), patch.object(sys, "argv", argv):
                gs.main()
            leaked = list(out_root.glob("**/submission_*"))
            self.assertEqual(leaked, [])
            self.assertTrue((practice / "grading_report.json").exists())
            self.assertTrue((practice / "feedback.md").exists())


if __name__ == "__main__":
    unittest.main()
