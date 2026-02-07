import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_upload_api_service import (
    ExamUploadApiDeps,
    ExamUploadApiError,
    exam_upload_confirm,
    exam_upload_draft,
    exam_upload_draft_save,
    exam_upload_status,
)


class _ConfirmError(Exception):
    def __init__(self, status_code: int, detail):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


class ExamUploadApiServiceTest(unittest.TestCase):
    def test_status_missing_job_raises_http_mappable_error(self):
        deps = ExamUploadApiDeps(
            load_exam_job=lambda _job_id: (_ for _ in ()).throw(FileNotFoundError()),
            exam_job_path=lambda _job_id: Path("/tmp/none"),
            load_exam_draft_override=lambda _job_dir: {},
            save_exam_draft_override=lambda *_args, **_kwargs: {},
            build_exam_upload_draft=lambda *_args, **_kwargs: {},
            exam_upload_not_ready_detail=lambda job, message: {"error": "job_not_ready", "status": job.get("status"), "message": message},
            parse_exam_answer_key_text=lambda _text: ([], []),
            read_text_safe=lambda _path, limit=6000: "",
            write_exam_job=lambda _job_id, _updates: None,
            confirm_exam_upload=lambda _job_id, _job, _job_dir: {"ok": True},
        )
        with self.assertRaises(ExamUploadApiError) as ctx:
            exam_upload_status("job-missing", deps=deps)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "job not found")

    def test_draft_requires_done_or_confirmed(self):
        deps = ExamUploadApiDeps(
            load_exam_job=lambda _job_id: {"status": "processing", "step": "ocr", "progress": 25},
            exam_job_path=lambda _job_id: Path("/tmp/none"),
            load_exam_draft_override=lambda _job_dir: {},
            save_exam_draft_override=lambda *_args, **_kwargs: {},
            build_exam_upload_draft=lambda *_args, **_kwargs: {},
            exam_upload_not_ready_detail=lambda job, message: {"error": "job_not_ready", "status": job.get("status"), "message": message},
            parse_exam_answer_key_text=lambda _text: ([], []),
            read_text_safe=lambda _path, limit=6000: "",
            write_exam_job=lambda _job_id, _updates: None,
            confirm_exam_upload=lambda _job_id, _job, _job_dir: {"ok": True},
        )
        with self.assertRaises(ExamUploadApiError) as ctx:
            exam_upload_draft("job-1", deps=deps)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual((ctx.exception.detail or {}).get("error"), "job_not_ready")

    def test_draft_save_bumps_version(self):
        writes = []
        saves = []
        deps = ExamUploadApiDeps(
            load_exam_job=lambda _job_id: {"status": "done", "draft_version": 2},
            exam_job_path=lambda _job_id: Path("/tmp/job-2"),
            load_exam_draft_override=lambda _job_dir: {"meta": {}},
            save_exam_draft_override=lambda *args, **kwargs: saves.append((args, kwargs)) or {},
            build_exam_upload_draft=lambda *_args, **_kwargs: {},
            exam_upload_not_ready_detail=lambda job, message: {"error": "job_not_ready", "status": job.get("status"), "message": message},
            parse_exam_answer_key_text=lambda _text: ([], []),
            read_text_safe=lambda _path, limit=6000: "",
            write_exam_job=lambda job_id, updates: writes.append((job_id, dict(updates))),
            confirm_exam_upload=lambda _job_id, _job, _job_dir: {"ok": True},
        )
        result = exam_upload_draft_save(
            job_id="job-2",
            meta={"class_name": "高二2403班"},
            questions=[{"question_id": "Q1"}],
            score_schema={"mode": "question"},
            answer_key_text="1 A",
            deps=deps,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("draft_version"), 3)
        self.assertEqual(writes, [("job-2", {"draft_version": 3})])
        self.assertEqual(len(saves), 1)

    def test_confirm_maps_confirm_error(self):
        deps = ExamUploadApiDeps(
            load_exam_job=lambda _job_id: {"status": "done"},
            exam_job_path=lambda _job_id: Path("/tmp/job-3"),
            load_exam_draft_override=lambda _job_dir: {},
            save_exam_draft_override=lambda *_args, **_kwargs: {},
            build_exam_upload_draft=lambda *_args, **_kwargs: {},
            exam_upload_not_ready_detail=lambda job, message: {"error": "job_not_ready", "status": job.get("status"), "message": message},
            parse_exam_answer_key_text=lambda _text: ([], []),
            read_text_safe=lambda _path, limit=6000: "",
            write_exam_job=lambda _job_id, _updates: None,
            confirm_exam_upload=lambda _job_id, _job, _job_dir: (_ for _ in ()).throw(
                _ConfirmError(400, {"error": "exam_id_conflict"})
            ),
        )
        with self.assertRaises(ExamUploadApiError) as ctx:
            exam_upload_confirm("job-3", deps=deps)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual((ctx.exception.detail or {}).get("error"), "exam_id_conflict")

    def test_draft_reads_parsed_and_builds_response(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            job_dir = root / "job-4"
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(json.dumps({"exam_id": "EX4"}), encoding="utf-8")
            (job_dir / "answer_text.txt").write_text("1 A", encoding="utf-8")
            calls = {}

            def _build(job_id, job, parsed, override, *, parse_exam_answer_key_text, answer_text_excerpt):  # type: ignore[no-untyped-def]
                calls["job_id"] = job_id
                calls["parsed"] = parsed
                calls["override"] = override
                calls["excerpt"] = answer_text_excerpt
                self.assertTrue(callable(parse_exam_answer_key_text))
                return {"exam_id": parsed.get("exam_id"), "job_id": job_id}

            deps = ExamUploadApiDeps(
                load_exam_job=lambda _job_id: {"status": "done"},
                exam_job_path=lambda _job_id: job_dir,
                load_exam_draft_override=lambda _job_dir: {"meta": {"class_name": "高二2403班"}},
                save_exam_draft_override=lambda *_args, **_kwargs: {},
                build_exam_upload_draft=_build,
                exam_upload_not_ready_detail=lambda job, message: {"error": "job_not_ready", "status": job.get("status"), "message": message},
                parse_exam_answer_key_text=lambda _text: ([], []),
                read_text_safe=lambda path, limit=6000: path.read_text(encoding="utf-8")[:limit],
                write_exam_job=lambda _job_id, _updates: None,
                confirm_exam_upload=lambda _job_id, _job, _job_dir: {"ok": True},
            )
            result = exam_upload_draft("job-4", deps=deps)
            self.assertTrue(result.get("ok"))
            self.assertEqual((result.get("draft") or {}).get("exam_id"), "EX4")
            self.assertEqual(calls.get("job_id"), "job-4")
            self.assertEqual(calls.get("excerpt"), "1 A")


if __name__ == "__main__":
    unittest.main()
