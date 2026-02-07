import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_range_service import (
    ExamRangeDeps,
    exam_question_batch_detail,
    exam_range_summary_batch,
    exam_range_top_students,
    normalize_question_no_list,
    parse_question_no_int,
)


class ExamRangeServiceTest(unittest.TestCase):
    def test_parse_and_normalize_question_no_helpers(self):
        self.assertEqual(parse_question_no_int("12"), 12)
        self.assertEqual(parse_question_no_int("12-1"), 12)
        self.assertIsNone(parse_question_no_int("Q"))
        self.assertEqual(normalize_question_no_list("1,2;2 3"), [1, 2, 3])

    def _deps(
        self,
        exam_id: str,
        responses_path: Path,
        questions_path: Path,
    ) -> ExamRangeDeps:
        def safe_int_arg(value, default, minimum, maximum):  # type: ignore[no-untyped-def]
            try:
                out = int(value)
            except Exception:
                out = default
            return max(minimum, min(maximum, out))

        def parse_score(value):  # type: ignore[no-untyped-def]
            try:
                text = str(value).strip()
                if not text:
                    return None
                return float(text)
            except Exception:
                return None

        def read_questions(_path):  # type: ignore[no-untyped-def]
            out = {}
            with questions_path.open(encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    out[str(row.get("question_id") or "").strip()] = {
                        "question_id": str(row.get("question_id") or "").strip(),
                        "question_no": str(row.get("question_no") or "").strip(),
                        "max_score": parse_score(row.get("max_score")),
                    }
            return out

        def question_detail(_exam_id, question_no=None, top_n=5, **kwargs):  # type: ignore[no-untyped-def]
            q_no = int(question_no or 0)
            if q_no == 1:
                return {
                    "ok": True,
                    "question": {"question_no": "1", "question_id": "Q1"},
                    "distribution": {"4": 1, "2": 1},
                    "sample_top_students": [{"student_id": "S1"}][:top_n],
                    "sample_bottom_students": [{"student_id": "S2"}][:top_n],
                    "response_count": 2,
                }
            return {"error": "question_not_found"}

        manifest = {"exam_id": exam_id}
        return ExamRangeDeps(
            load_exam_manifest=lambda _exam_id: manifest if _exam_id == exam_id else {},
            exam_responses_path=lambda _manifest: responses_path,
            exam_questions_path=lambda _manifest: questions_path,
            read_questions_csv=read_questions,
            parse_score_value=parse_score,
            safe_int_arg=safe_int_arg,
            exam_question_detail=question_detail,
        )

    def test_range_top_students_and_batch(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            responses_path = root / "responses_scored.csv"
            questions_path = root / "questions.csv"
            exam_id = "EX1"

            with responses_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["exam_id", "student_id", "student_name", "class_name", "question_id", "question_no", "score"])
                writer.writerow([exam_id, "S1", "A", "C1", "Q1", "1", "4"])
                writer.writerow([exam_id, "S1", "A", "C1", "Q2", "2", "3"])
                writer.writerow([exam_id, "S2", "B", "C1", "Q1", "1", "2"])
                writer.writerow([exam_id, "S2", "B", "C1", "Q2", "2", "1"])

            with questions_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["question_id", "question_no", "max_score"])
                writer.writerow(["Q1", "1", "4"])
                writer.writerow(["Q2", "2", "4"])

            deps = self._deps(exam_id, responses_path, questions_path)
            out = exam_range_top_students(exam_id, 1, 2, top_n=2, deps=deps)
            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("summary", {}).get("max_score"), 7.0)
            self.assertEqual(out.get("summary", {}).get("min_score"), 3.0)
            self.assertEqual(out.get("top_students", [])[0].get("student_id"), "S1")

            batch = exam_range_summary_batch(
                exam_id,
                [
                    {"label": "Q1", "start_question_no": 1, "end_question_no": 1},
                    {"label": "bad", "start_question_no": "x", "end_question_no": 2},
                ],
                top_n=2,
                deps=deps,
            )
            self.assertTrue(batch.get("ok"))
            self.assertEqual(batch.get("range_count_succeeded"), 1)
            self.assertEqual(batch.get("range_count_failed"), 1)

    def test_question_batch_detail_collects_missing(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            responses_path = root / "responses_scored.csv"
            questions_path = root / "questions.csv"
            exam_id = "EX1"
            responses_path.write_text("exam_id,student_id,question_id,question_no,score\n", encoding="utf-8")
            questions_path.write_text("question_id,question_no,max_score\nQ1,1,4\n", encoding="utf-8")

            deps = self._deps(exam_id, responses_path, questions_path)
            out = exam_question_batch_detail(exam_id, [1, 2], top_n=1, deps=deps)
            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("question_count_succeeded"), 1)
            self.assertEqual(out.get("question_count_failed"), 1)
            self.assertEqual(out.get("missing_question_nos"), [2])


if __name__ == "__main__":
    unittest.main()
