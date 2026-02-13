import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_upload_legacy_service import (
    AssignmentUploadLegacyDeps,
    AssignmentUploadLegacyError,
    assignment_upload,
)


@dataclass
class _Upload:
    filename: str
    content: bytes


class AssignmentUploadLegacyServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_requires_source_files(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentUploadLegacyDeps(
                data_dir=root / "data",
                parse_date_str=lambda value: str(value or "2026-02-07"),
                sanitize_filename=lambda name: str(name or "").strip(),
                save_upload_file=self._save_upload,
                extract_text_from_pdf=lambda _p, _l, _o: "",
                extract_text_from_image=lambda _p, _l, _o: "",
                llm_parse_assignment_payload=lambda _s, _a: {},
                write_uploaded_questions=lambda _o, _aid, _q: [],
                compute_requirements_missing=lambda _r: [],
                llm_autofill_requirements=lambda s, a, q, r, m: (r, m, False),
                save_assignment_requirements=lambda *args, **kwargs: {"ok": True},
                parse_ids_value=lambda _v: [],
                resolve_scope=lambda _s, _ids, _c: "public",
                load_assignment_meta=lambda _o: {},
                now_iso=lambda: "2026-02-07T10:00:00",
            )
            with self.assertRaises(AssignmentUploadLegacyError) as ctx:
                await assignment_upload(
                    deps=deps,
                    assignment_id="A1",
                    date="2026-02-07",
                    scope="public",
                    class_name="",
                    student_ids="",
                    files=[],
                    answer_files=None,
                    ocr_mode="FREE_OCR",
                    language="zh",
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "No source files uploaded")

    async def test_raises_when_source_text_empty(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentUploadLegacyDeps(
                data_dir=root / "data",
                parse_date_str=lambda value: str(value or "2026-02-07"),
                sanitize_filename=lambda name: str(name or "").strip(),
                save_upload_file=self._save_upload,
                extract_text_from_pdf=lambda _p, _l, _o: "",
                extract_text_from_image=lambda _p, _l, _o: "",
                llm_parse_assignment_payload=lambda _s, _a: {},
                write_uploaded_questions=lambda _o, _aid, _q: [],
                compute_requirements_missing=lambda _r: [],
                llm_autofill_requirements=lambda s, a, q, r, m: (r, m, False),
                save_assignment_requirements=lambda *args, **kwargs: {"ok": True},
                parse_ids_value=lambda _v: [],
                resolve_scope=lambda _s, _ids, _c: "public",
                load_assignment_meta=lambda _o: {},
                now_iso=lambda: "2026-02-07T10:00:00",
            )
            with self.assertRaises(AssignmentUploadLegacyError) as ctx:
                await assignment_upload(
                    deps=deps,
                    assignment_id="A1",
                    date="2026-02-07",
                    scope="public",
                    class_name="",
                    student_ids="",
                    files=[_Upload(filename="q1.png", content=b"fake")],
                    answer_files=None,
                    ocr_mode="FREE_OCR",
                    language="zh",
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail.get("error"), "source_text_empty")

    async def test_success_flow_writes_meta_and_returns_ok(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentUploadLegacyDeps(
                data_dir=root / "data",
                parse_date_str=lambda value: str(value or "2026-02-07"),
                sanitize_filename=lambda name: str(name or "").strip(),
                save_upload_file=self._save_upload,
                extract_text_from_pdf=lambda _p, _l, _o: "x" * 260,
                extract_text_from_image=lambda _p, _l, _o: "x" * 260,
                llm_parse_assignment_payload=lambda _s, _a: {
                    "questions": [{"stem": "q1", "answer": "a1"}],
                    "requirements": {"core_concepts": ["牛顿定律"]},
                },
                write_uploaded_questions=lambda _o, _aid, _q: [{"question_id": "UP-001"}],
                compute_requirements_missing=lambda _r: [],
                llm_autofill_requirements=lambda s, a, q, r, m: (r, m, False),
                save_assignment_requirements=lambda *args, **kwargs: {"ok": True},
                parse_ids_value=lambda _v: [],
                resolve_scope=lambda _s, _ids, _c: "public",
                load_assignment_meta=lambda _o: {},
                now_iso=lambda: "2026-02-07T10:00:00",
            )
            result = await assignment_upload(
                deps=deps,
                assignment_id="A1",
                date="2026-02-07",
                scope="public",
                class_name="",
                student_ids="",
                files=[_Upload(filename="q1.png", content=b"fake")],
                answer_files=None,
                ocr_mode="FREE_OCR",
                language="zh",
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("question_count"), 1)
            meta_path = root / "data" / "assignments" / "A1" / "meta.json"
            self.assertTrue(meta_path.exists())

    async def test_rejects_invalid_assignment_id_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentUploadLegacyDeps(
                data_dir=root / "data",
                parse_date_str=lambda value: str(value or "2026-02-07"),
                sanitize_filename=lambda name: str(name or "").strip(),
                save_upload_file=self._save_upload,
                extract_text_from_pdf=lambda _p, _l, _o: "x" * 260,
                extract_text_from_image=lambda _p, _l, _o: "x" * 260,
                llm_parse_assignment_payload=lambda _s, _a: {"questions": [{"stem": "q1"}], "requirements": {}},
                write_uploaded_questions=lambda _o, _aid, _q: [{"question_id": "UP-001"}],
                compute_requirements_missing=lambda _r: [],
                llm_autofill_requirements=lambda s, a, q, r, m: (r, m, False),
                save_assignment_requirements=lambda *args, **kwargs: {"ok": True},
                parse_ids_value=lambda _v: [],
                resolve_scope=lambda _s, _ids, _c: "public",
                load_assignment_meta=lambda _o: {},
                now_iso=lambda: "2026-02-07T10:00:00",
            )
            with self.assertRaises(AssignmentUploadLegacyError) as ctx:
                await assignment_upload(
                    deps=deps,
                    assignment_id="../escape",
                    date="2026-02-07",
                    scope="public",
                    class_name="",
                    student_ids="",
                    files=[_Upload(filename="q1.png", content=b"fake")],
                    answer_files=None,
                    ocr_mode="FREE_OCR",
                    language="zh",
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "invalid assignment_id")

    async def test_rejects_unsupported_source_file_type(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentUploadLegacyDeps(
                data_dir=root / "data",
                parse_date_str=lambda value: str(value or "2026-02-07"),
                sanitize_filename=lambda name: str(name or "").strip(),
                save_upload_file=self._save_upload,
                extract_text_from_pdf=lambda _p, _l, _o: "x" * 260,
                extract_text_from_image=lambda _p, _l, _o: "x" * 260,
                llm_parse_assignment_payload=lambda _s, _a: {"questions": [{"stem": "q1"}], "requirements": {}},
                write_uploaded_questions=lambda _o, _aid, _q: [{"question_id": "UP-001"}],
                compute_requirements_missing=lambda _r: [],
                llm_autofill_requirements=lambda s, a, q, r, m: (r, m, False),
                save_assignment_requirements=lambda *args, **kwargs: {"ok": True},
                parse_ids_value=lambda _v: [],
                resolve_scope=lambda _s, _ids, _c: "public",
                load_assignment_meta=lambda _o: {},
                now_iso=lambda: "2026-02-07T10:00:00",
            )
            with self.assertRaises(AssignmentUploadLegacyError) as ctx:
                await assignment_upload(
                    deps=deps,
                    assignment_id="A1",
                    date="2026-02-07",
                    scope="public",
                    class_name="",
                    student_ids="",
                    files=[_Upload(filename="evil.exe", content=b"fake")],
                    answer_files=None,
                    ocr_mode="FREE_OCR",
                    language="zh",
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("不支持的文件类型", str(ctx.exception.detail))

    async def _save_upload(self, upload: _Upload, dest: Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(upload.content)


if __name__ == "__main__":
    unittest.main()
