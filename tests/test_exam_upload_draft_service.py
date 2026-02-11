import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_upload_draft_service import (
    build_exam_upload_draft,
    exam_upload_not_ready_detail,
    load_exam_draft_override,
    save_exam_draft_override,
)


class ExamUploadDraftServiceTest(unittest.TestCase):
    def test_not_ready_detail_contains_progress(self):
        detail = exam_upload_not_ready_detail(
            {"status": "processing", "step": "parse_scores", "progress": 35},
            "解析尚未完成，暂无法打开草稿。",
        )
        self.assertEqual(detail.get("error"), "job_not_ready")
        self.assertEqual(detail.get("status"), "processing")
        self.assertEqual(detail.get("step"), "parse_scores")
        self.assertEqual(detail.get("progress"), 35)

    def test_save_and_load_override_roundtrip(self):
        with TemporaryDirectory() as td:
            job_dir = Path(td)
            saved = save_exam_draft_override(
                job_dir,
                {},
                meta={"class_name": "高二2403班"},
                questions=[{"question_id": "Q1", "max_score": 5}],
                score_schema={"mode": "question"},
                answer_key_text="1 A",
            )
            loaded = load_exam_draft_override(job_dir)
            self.assertEqual(loaded, saved)
            self.assertEqual(loaded.get("meta", {}).get("class_name"), "高二2403班")
            self.assertEqual(loaded.get("answer_key_text"), "1 A")

    def test_build_draft_applies_override_answer_key(self):
        parsed = {
            "exam_id": "EX1",
            "meta": {"date": "2026-02-07", "class_name": "高二2403班"},
            "paper_files": ["paper.pdf"],
            "score_files": ["scores.xlsx"],
            "answer_files": [],
            "counts": {"students": 2},
            "questions": [{"question_id": "Q1", "max_score": 4}],
            "warnings": [],
            "answer_key": {"count": 0},
            "scoring": {"status": "unscored"},
            "counts_scored": {"students": 0},
            "totals_summary": {"avg_total": 0},
        }
        job = {"exam_id": "EX1", "date": "2026-02-07", "class_name": "高二2403班", "draft_version": 1}
        override = {
            "meta": {"class_name": "高二2404班"},
            "questions": [{"question_id": "Q1", "max_score": 5}],
            "answer_key_text": "1 A\n2 C",
        }

        def parse_answer_key(_text: str):
            return ([{"question_id": "Q1"}, {"question_id": "Q2"}], [])

        draft = build_exam_upload_draft(
            "job-1",
            job,
            parsed,
            override,
            parse_exam_answer_key_text=parse_answer_key,
            answer_text_excerpt="",
        )
        self.assertEqual(draft.get("class_name"), "高二2404班")
        self.assertEqual(draft.get("answer_key", {}).get("source"), "override")
        self.assertEqual(draft.get("answer_key", {}).get("count"), 2)
        self.assertEqual(draft.get("questions"), [{"question_id": "Q1", "max_score": 5}])

    def test_build_draft_exposes_needs_confirm_and_override_confirm_flag(self):
        parsed = {
            "exam_id": "EX1",
            "meta": {"date": "2026-02-07", "class_name": "高二2403班"},
            "paper_files": ["paper.pdf"],
            "score_files": ["scores.xlsx"],
            "answer_files": [],
            "counts": {"students": 2},
            "questions": [{"question_id": "SUBJECT_PHYSICS", "max_score": 60}],
            "warnings": [],
            "answer_key": {"count": 0},
            "scoring": {"status": "scored"},
            "counts_scored": {"students": 2},
            "totals_summary": {"avg_total": 38.5},
            "score_schema": {"needs_confirm": True, "subject": {"coverage": 0.5}},
            "needs_confirm": True,
        }
        job = {"exam_id": "EX1", "date": "2026-02-07", "class_name": "高二2403班", "draft_version": 1}

        draft = build_exam_upload_draft(
            "job-1",
            job,
            parsed,
            {"score_schema": {"subject": {"selected_candidate_id": "pair:4:5"}}},
            parse_exam_answer_key_text=lambda _text: ([], []),
            answer_text_excerpt="",
        )
        self.assertFalse(bool(draft.get("needs_confirm")))
        self.assertEqual(float((((draft.get("score_schema") or {}).get("subject") or {}).get("coverage") or 0.0)), 0.5)
        self.assertEqual(
            str((((draft.get("score_schema") or {}).get("subject") or {}).get("selected_candidate_id") or "")),
            "pair:4:5",
        )

    def test_build_draft_sets_suggested_candidate_when_missing_selection(self):
        parsed = {
            "exam_id": "EX1",
            "meta": {"date": "2026-02-07", "class_name": "高二2403班"},
            "paper_files": ["paper.pdf"],
            "score_files": ["scores.xlsx"],
            "answer_files": [],
            "counts": {"students": 2},
            "questions": [{"question_id": "SUBJECT_PHYSICS", "max_score": 60}],
            "warnings": [],
            "answer_key": {"count": 0},
            "scoring": {"status": "scored"},
            "counts_scored": {"students": 2},
            "totals_summary": {"avg_total": 38.5},
            "score_schema": {
                "needs_confirm": True,
                "subject": {
                    "coverage": 0.7,
                    "recommended_candidate_id": "pair:4:5",
                },
            },
            "needs_confirm": True,
        }
        job = {"exam_id": "EX1", "date": "2026-02-07", "class_name": "高二2403班", "draft_version": 1}

        draft = build_exam_upload_draft(
            "job-1",
            job,
            parsed,
            {},
            parse_exam_answer_key_text=lambda _text: ([], []),
            answer_text_excerpt="",
        )
        subject_info = ((draft.get("score_schema") or {}).get("subject") or {})
        self.assertEqual(str(subject_info.get("suggested_selected_candidate_id") or ""), "pair:4:5")
        self.assertTrue(bool(draft.get("needs_confirm")))

    def test_build_draft_invalid_selected_candidate_keeps_needs_confirm(self):
        parsed = {
            "exam_id": "EX1",
            "meta": {"date": "2026-02-07", "class_name": "高二2403班"},
            "paper_files": ["paper.pdf"],
            "score_files": ["scores.xlsx"],
            "answer_files": [],
            "counts": {"students": 2},
            "questions": [{"question_id": "SUBJECT_PHYSICS", "max_score": 60}],
            "warnings": [],
            "answer_key": {"count": 0},
            "scoring": {"status": "scored"},
            "counts_scored": {"students": 2},
            "totals_summary": {"avg_total": 38.5},
            "score_schema": {
                "needs_confirm": True,
                "subject": {
                    "coverage": 0.6,
                    "selected_candidate_available": False,
                    "selection_error": "selected_candidate_not_found",
                },
            },
            "needs_confirm": True,
        }
        job = {"exam_id": "EX1", "date": "2026-02-07", "class_name": "高二2403班", "draft_version": 1}

        draft = build_exam_upload_draft(
            "job-1",
            job,
            parsed,
            {"score_schema": {"subject": {"selected_candidate_id": "pair:4:5"}}},
            parse_exam_answer_key_text=lambda _text: ([], []),
            answer_text_excerpt="",
        )
        self.assertTrue(bool(draft.get("needs_confirm")))


if __name__ == "__main__":
    unittest.main()
