import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_upload_confirm_service import (
    ExamUploadConfirmDeps,
    ExamUploadConfirmError,
    confirm_exam_upload,
)


class ExamUploadConfirmServiceTest(unittest.TestCase):
    def _deps(self, root: Path, writes: list):  # type: ignore[no-untyped-def]
        def write_exam_job(job_id, updates):  # type: ignore[no-untyped-def]
            writes.append((job_id, dict(updates)))
            return updates

        return ExamUploadConfirmDeps(
            app_root=root,
            data_dir=root / "data",
            now_iso=lambda: "2026-02-08T12:00:00",
            write_exam_job=write_exam_job,
            load_exam_draft_override=lambda _job_dir: {},
            parse_exam_answer_key_text=lambda _text: ([], []),
            write_exam_questions_csv=lambda _path, _questions, max_scores=None: None,
            write_exam_answers_csv=lambda _path, _answers: None,
            load_exam_answer_key_from_csv=lambda _path: {},
            ensure_questions_max_score=lambda _path, _qids, default_score=1.0: None,
            apply_answer_key_to_responses_csv=lambda _a, _b, _c, _d: {},
            run_script=lambda _cmd: None,
            diag_log=lambda _event, _payload=None: None,
            copy2=lambda src, dst: dst.write_bytes(src.read_bytes()),
        )

    def test_missing_parsed_marks_failed_and_raises(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "exam_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            deps = self._deps(root, writes)

            with self.assertRaises(ExamUploadConfirmError) as ctx:
                confirm_exam_upload("job-1", {"exam_id": "EX1"}, job_dir, deps)
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "parsed result missing")
            self.assertEqual(writes[-1][1].get("status"), "failed")
            self.assertEqual(writes[-1][1].get("error"), "parsed result missing")

    def test_manifest_exists_marks_confirmed_and_raises_409(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "exam_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            parsed = {"exam_id": "EX1", "meta": {}, "counts": {}}
            (job_dir / "parsed.json").write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
            exam_dir = root / "data" / "exams" / "EX1"
            exam_dir.mkdir(parents=True, exist_ok=True)
            (exam_dir / "manifest.json").write_text("{}", encoding="utf-8")

            deps = self._deps(root, writes)
            with self.assertRaises(ExamUploadConfirmError) as ctx:
                confirm_exam_upload("job-1", {"exam_id": "EX1"}, job_dir, deps)
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(ctx.exception.detail, "exam already exists")
            self.assertEqual(writes[-1][1].get("status"), "confirmed")

    def test_success_writes_manifest_and_returns_ok(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "exam_jobs" / "job-1"
            (job_dir / "derived").mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(
                json.dumps({"exam_id": "EX1", "meta": {"class_name": "高二2403班"}, "counts": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (job_dir / "derived" / "responses_scored.csv").write_text("student_id,question_id,score\ns1,Q1,1\n", encoding="utf-8")

            deps = self._deps(root, writes)
            result = confirm_exam_upload("job-1", {"exam_id": "EX1"}, job_dir, deps)
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("exam_id"), "EX1")
            manifest_path = root / "data" / "exams" / "EX1" / "manifest.json"
            self.assertTrue(manifest_path.exists())
            self.assertEqual(writes[-1][1].get("status"), "confirmed")

    def test_rejects_invalid_exam_id_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "exam_jobs" / "job-1"
            (job_dir / "derived").mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(
                json.dumps({"exam_id": "../escape", "meta": {}, "counts": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (job_dir / "derived" / "responses_scored.csv").write_text("student_id,question_id,score\ns1,Q1,1\n", encoding="utf-8")

            deps = self._deps(root, writes)
            with self.assertRaises(ExamUploadConfirmError) as ctx:
                confirm_exam_upload("job-1", {"exam_id": "../escape"}, job_dir, deps)
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "invalid exam_id")
            self.assertEqual(writes[-1][1].get("status"), "failed")


if __name__ == "__main__":
    unittest.main()
