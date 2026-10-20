import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import grade_submission as gs
from scripts import render_assignment_pdf as rap


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

    def test_get_expected_answer_rejects_absolute_path_outside_jail(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            secret = root / "tmp" / "outside_answer.md"
            secret.parent.mkdir(parents=True)
            secret.write_text("答案：SECRET_OUTSIDE_ANSWER", encoding="utf-8")
            opened: list[str] = []
            original_read = Path.read_text

            def tracking_read(self, *args, **kwargs):
                opened.append(str(self))
                return original_read(self, *args, **kwargs)

            row = {"answer_ref": str(secret)}
            with patch.object(Path, "read_text", tracking_read):
                expected = gs.get_expected_answer(
                    row, folder=folder, app_root=root, data_dir=root
                )
            self.assertEqual(expected, "")
            self.assertTrue(all("outside_answer" not in path for path in opened))

    def test_get_expected_answer_rejects_symlink_escape(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            secret = root / "tmp" / "secret.md"
            secret.parent.mkdir(parents=True)
            secret.write_text("答案：LEAKED_SYMLINK", encoding="utf-8")
            link = folder / "answers" / "escape.md"
            link.parent.mkdir(parents=True)
            link.symlink_to(secret)
            expected = gs.get_expected_answer(
                {"answer_ref": str(link)},
                folder=folder,
                app_root=root,
                data_dir=root,
            )
            self.assertEqual(expected, "")
            self.assertNotIn("LEAKED_SYMLINK", expected)

    def test_get_expected_answer_reads_bank_and_folder(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            local = folder / "answers" / "local.md"
            local.parent.mkdir(parents=True)
            local.write_text("答案：FOLDER7", encoding="utf-8")
            bank = root / "question_bank" / "answers" / "bank.md"
            bank.parent.mkdir(parents=True)
            bank.write_text("答案：BANK42", encoding="utf-8")
            folder_expected = gs.get_expected_answer(
                {"answer_ref": "answers/local.md"},
                folder=folder,
                app_root=root,
                data_dir=root,
            )
            bank_expected = gs.get_expected_answer(
                {"answer_ref": str(bank)},
                folder=folder,
                app_root=root,
                data_dir=root,
            )
            self.assertIn("FOLDER7", folder_expected)
            self.assertIn("BANK42", bank_expected)

    def test_evaluate_question_jailout_answer_ref_does_not_load_outside_rubric(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            outside_answer = root / "tmp" / "secret_answer.md"
            outside_answer.parent.mkdir(parents=True)
            outside_answer.write_text("答案：SECRET_ANSWER", encoding="utf-8")
            outside_rubric = root / "tmp" / "secret_rubric.json"
            outside_rubric.write_text(
                '{"steps":[{"id":"leak","keywords":["should_not_grade"],"score":1}]}',
                encoding="utf-8",
            )
            opened: list[str] = []
            original_read = Path.read_text

            def tracking_read(self, *args, **kwargs):
                opened.append(str(self))
                return original_read(self, *args, **kwargs)

            question = {
                "question_id": "Q1",
                "answer_ref": str(outside_answer),
                "rubric_ref": str(outside_rubric),
            }
            with patch.object(Path, "read_text", tracking_read):
                result = gs.evaluate_question(
                    question=question,
                    block_text="should_not_grade",
                    adapter=None,
                    llm_grade=False,
                    llm_confidence_threshold=0.6,
                    folder=folder,
                    app_root=root,
                    data_dir=root,
                )
            self.assertEqual(result["reason"], "missing_expected")
            self.assertEqual(result["status"], "ungraded")
            self.assertTrue(all("secret_rubric" not in path for path in opened))
            self.assertTrue(all("secret_answer" not in path for path in opened))

    def test_pack_id_uses_data_dir_assignments_root_not_script_root(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            decoy_root = tmp / "decoy_root"
            decoy_folder = decoy_root / "data" / "assignments" / "HW_PACK"
            decoy_folder.mkdir(parents=True)
            (decoy_folder / "meta.json").write_text(
                '{"pack_id": "decoy_pack"}', encoding="utf-8"
            )
            (decoy_folder / "questions.csv").write_text(
                "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
                "Q_DECOY,力学,basic,open,,,,\n",
                encoding="utf-8",
            )
            data_dir = tmp / "real_data"
            real_folder = data_dir / "assignments" / "HW_PACK"
            real_folder.mkdir(parents=True)
            (real_folder / "meta.json").write_text(
                '{"pack_id": "real_pack"}', encoding="utf-8"
            )
            (real_folder / "questions.csv").write_text(
                "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
                "Q_REAL,力学,basic,open,,,,\n",
                encoding="utf-8",
            )
            upload = tmp / "page.png"
            upload.write_bytes(b"x")
            out_root = tmp / "student_submissions"
            captured: dict[str, str] = {}

            def fake_ocr(_files, out_dir, _language, _mode):
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "page_1.txt").write_text("答案：1", encoding="utf-8")
                return "答案：1"

            def fake_load(pack_id):
                captured["pack_id"] = pack_id
                return None

            argv = [
                "grade_submission.py",
                "--student-id",
                "S1",
                "--assignment-id",
                "HW_PACK",
                "--out-dir",
                str(out_root),
                "--files",
                str(upload),
                "--skip-profile-update",
                "--data-dir",
                str(data_dir),
                "--app-root",
                str(tmp),
            ]
            with (
                patch.object(gs, "ocr_files", fake_ocr),
                patch.object(gs, "load_grade_adapter", fake_load),
                patch.object(gs, "ROOT", decoy_root),
                patch.object(sys, "argv", argv),
            ):
                gs.main()
            self.assertEqual(captured.get("pack_id"), "real_pack")
            reports = list(out_root.glob("**/grading_report.json"))
            self.assertTrue(reports)
            payload = reports[0].read_text(encoding="utf-8")
            self.assertIn("Q_REAL", payload)
            self.assertNotIn("Q_DECOY", payload)

    def test_stem_text_for_pdf_jailout_returns_chinese_fallback_without_reading_secret(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            secret = root / "tmp" / "outside_stem.md"
            secret.parent.mkdir(parents=True)
            secret.write_text("SECRET_OUTSIDE_STEM", encoding="utf-8")
            opened: list[str] = []
            original_read = Path.read_text

            def tracking_read(self, *args, **kwargs):
                opened.append(str(self))
                return original_read(self, *args, **kwargs)

            with patch.object(Path, "read_text", tracking_read):
                text = rap.stem_text_for_pdf(
                    str(secret), folder=folder, app_root=root, data_dir=root
                )
            self.assertEqual(text, "[题干缺失] 请补充题干。")
            self.assertNotIn("SECRET_OUTSIDE_STEM", text)
            self.assertTrue(all("outside_stem" not in path for path in opened))

    def test_render_pdf_missing_stem_fallback_on_jailout(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "HW1"
            folder.mkdir(parents=True)
            secret = root / "tmp" / "outside_stem.md"
            secret.parent.mkdir(parents=True)
            secret.write_text("SECRET_OUTSIDE_STEM", encoding="utf-8")
            out_pdf = root / "out.pdf"
            questions = [
                {
                    "question_id": "Q1",
                    "kp_id": "kp.x",
                    "difficulty": "basic",
                    "stem_ref": str(secret),
                }
            ]
            try:
                rap.render_pdf(
                    "HW1",
                    questions,
                    out_pdf,
                    folder=folder,
                    app_root=root,
                    data_dir=root,
                )
            except SystemExit as exc:
                self.fail(f"render_pdf exited {exc.code}")
            self.assertTrue(out_pdf.is_file())
            data = out_pdf.read_bytes()
            self.assertNotIn(b"SECRET_OUTSIDE_STEM", data)
            self.assertNotIn(str(secret).encode("utf-8"), data)


if __name__ == "__main__":
    unittest.main()
