import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_upload_start_service import ExamUploadStartDeps, start_exam_upload


class _FakeUpload:
    def __init__(self, filename: str, payload: bytes):
        self.filename = filename
        self.payload = payload


class ExamUploadStartServiceTest(unittest.IsolatedAsyncioTestCase):
    def _deps(self, root: Path, writes: list, queued: list):
        async def save_upload_file(upload, dest):  # type: ignore[no-untyped-def]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(upload.payload)

        def write_exam_job(job_id, updates, overwrite=False):  # type: ignore[no-untyped-def]
            writes.append((job_id, dict(updates), bool(overwrite)))
            return updates

        return ExamUploadStartDeps(
            parse_date_str=lambda raw: str(raw or ""),
            exam_job_path=lambda job_id: root / "exam_jobs" / job_id,
            sanitize_filename=lambda name: str(name or "").strip().replace("/", "_"),
            save_upload_file=save_upload_file,
            write_exam_job=write_exam_job,
            enqueue_exam_job=lambda job_id: queued.append(job_id),
            now_iso=lambda: "2026-02-08T12:00:00",
            diag_log=lambda _event, _payload=None: None,
            uuid_hex=lambda: "abcdef1234567890",
        )

    async def test_start_exam_upload_writes_record_and_enqueues(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            queued = []
            deps = self._deps(root, writes, queued)
            result = await start_exam_upload(
                exam_id="EX1",
                date="2026-02-08",
                class_name="高二2403班",
                paper_files=[_FakeUpload("paper.pdf", b"paper")],
                score_files=[_FakeUpload("scores.xlsx", b"score")],
                answer_files=[_FakeUpload("answers.pdf", b"ans")],
                ocr_mode="FREE_OCR",
                language="zh",
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("job_id"), "job_abcdef123456")
            self.assertEqual(queued, ["job_abcdef123456"])
            self.assertTrue(writes)
            record = writes[-1][1]
            self.assertEqual(record.get("paper_files"), ["paper.pdf"])
            self.assertEqual(record.get("score_files"), ["scores.xlsx"])
            self.assertEqual(record.get("answer_files"), ["answers.pdf"])

    async def test_start_exam_upload_requires_paper_and_scores(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            queued = []
            deps = self._deps(root, writes, queued)
            with self.assertRaises(ValueError):
                await start_exam_upload(
                    exam_id="EX1",
                    date="2026-02-08",
                    class_name="",
                    paper_files=[],
                    score_files=[_FakeUpload("scores.xlsx", b"score")],
                    answer_files=None,
                    ocr_mode="FREE_OCR",
                    language="zh",
                    deps=deps,
                )
            with self.assertRaises(ValueError):
                await start_exam_upload(
                    exam_id="EX1",
                    date="2026-02-08",
                    class_name="",
                    paper_files=[_FakeUpload("paper.pdf", b"paper")],
                    score_files=[],
                    answer_files=None,
                    ocr_mode="FREE_OCR",
                    language="zh",
                    deps=deps,
                )


if __name__ == "__main__":
    unittest.main()
