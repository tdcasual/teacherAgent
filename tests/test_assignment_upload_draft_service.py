import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_upload_draft_service import (
    assignment_upload_not_ready_detail,
    build_assignment_upload_draft,
    clean_assignment_draft_questions,
    load_assignment_draft_override,
    save_assignment_draft_override,
)


class AssignmentUploadDraftServiceTest(unittest.TestCase):
    def test_not_ready_detail_contains_progress(self):
        detail = assignment_upload_not_ready_detail(
            {"status": "processing", "step": "ocr", "progress": 35},
            "解析尚未完成，暂无法打开草稿。",
        )
        self.assertEqual(detail.get("error"), "job_not_ready")
        self.assertEqual(detail.get("status"), "processing")
        self.assertEqual(detail.get("step"), "ocr")
        self.assertEqual(detail.get("progress"), 35)

    def test_save_and_load_override_roundtrip(self):
        with TemporaryDirectory() as td:
            job_dir = Path(td)
            saved = save_assignment_draft_override(
                job_dir,
                {},
                requirements={"subject": "物理"},
                questions=[{"stem": "Q1"}],
                requirements_missing=["topic"],
                now_iso=lambda: "2026-02-08T12:00:00",
            )
            loaded = load_assignment_draft_override(job_dir)
            self.assertEqual(loaded, saved)
            self.assertEqual(loaded.get("requirements", {}).get("subject"), "物理")
            self.assertEqual(loaded.get("requirements_missing"), ["topic"])

    def test_build_draft_applies_override_and_missing_markers(self):
        parsed = {
            "questions": [{"stem": "原题"}],
            "requirements": {"subject": "物理", "topic": ""},
            "missing": ["topic"],
            "warnings": ["w1"],
            "delivery_mode": "pdf",
            "autofilled": False,
        }
        job = {
            "assignment_id": "HW_1",
            "date": "2026-02-08",
            "scope": "class",
            "class_name": "高二2403班",
            "student_ids": [],
            "source_files": ["paper.pdf"],
            "answer_files": [],
            "delivery_mode": "pdf",
            "draft_version": 2,
        }
        override = {
            "questions": [{"stem": "改后题"}],
            "requirements": {"topic": "欧姆定律"},
            "requirements_missing": ["extra_flag"],
        }

        def merge_requirements(base, update, overwrite=False):  # type: ignore[no-untyped-def]
            merged = dict(base)
            if overwrite:
                merged.update(update)
            else:
                for key, value in update.items():
                    if key not in merged:
                        merged[key] = value
            return merged

        def compute_missing(req):  # type: ignore[no-untyped-def]
            return [] if req.get("topic") else ["topic"]

        def parse_list_value(value):  # type: ignore[no-untyped-def]
            if isinstance(value, list):
                return [str(v) for v in value]
            return []

        draft = build_assignment_upload_draft(
            "job-1",
            job,
            parsed,
            override,
            merge_requirements=merge_requirements,
            compute_requirements_missing=compute_missing,
            parse_list_value=parse_list_value,
        )
        self.assertEqual(draft.get("assignment_id"), "HW_1")
        self.assertEqual(draft.get("question_count"), 1)
        self.assertEqual(draft.get("questions"), [{"stem": "改后题"}])
        self.assertEqual(draft.get("requirements", {}).get("topic"), "欧姆定律")
        self.assertIn("extra_flag", draft.get("requirements_missing", []))
        self.assertEqual(draft.get("draft_version"), 2)

    def test_clean_questions_strips_stem_and_skips_non_dict(self):
        cleaned = clean_assignment_draft_questions(
            [
                {"stem": "  a  ", "score": 5},
                42,
                {"stem": "", "score": 3},
            ]
        )
        self.assertEqual(cleaned, [{"stem": "a", "score": 5}, {"stem": "", "score": 3}])


if __name__ == "__main__":
    unittest.main()
