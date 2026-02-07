import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_detail_service import ExamDetailDeps, exam_question_detail, exam_student_detail


def _write_rows(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "exam_id",
                "student_id",
                "student_name",
                "class_name",
                "question_id",
                "question_no",
                "sub_no",
                "raw_label",
                "raw_value",
                "raw_answer",
                "score",
                "is_correct",
            ]
        )
        writer.writerow(["EX1", "S1", "Alex", "C1", "Q1", "1", "", "1", "4", "", "4", "1"])
        writer.writerow(["EX1", "S1", "Alex", "C1", "Q2", "2", "", "2", "3", "", "3", "1"])
        writer.writerow(["EX1", "S2", "Alex", "C2", "Q1", "1", "", "1", "2", "", "2", "0"])


def _read_questions_csv(path: Path):
    out = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = str(row.get("question_id") or "").strip()
            if not qid:
                continue
            try:
                max_score = float(str(row.get("max_score") or "").strip())
            except Exception:
                max_score = None
            out[qid] = {
                "question_id": qid,
                "question_no": str(row.get("question_no") or "").strip(),
                "max_score": max_score,
            }
    return out


def _parse_score_value(value):
    try:
        return float(str(value).strip())
    except Exception:
        return None


def _safe_int_arg(value, default=5, minimum=1, maximum=100):
    try:
        out = int(value)
    except Exception:
        out = default
    return max(minimum, min(maximum, out))


class ExamDetailServiceTest(unittest.TestCase):
    def _build_deps(self, responses_path: Path, questions_path: Path):
        def _load_manifest(exam_id: str):
            return {"exam_id": exam_id} if exam_id == "EX1" else {}

        return ExamDetailDeps(
            load_exam_manifest=_load_manifest,
            exam_responses_path=lambda _manifest: responses_path,
            exam_questions_path=lambda _manifest: questions_path,
            read_questions_csv=_read_questions_csv,
            parse_score_value=_parse_score_value,
            safe_int_arg=_safe_int_arg,
        )

    def test_exam_student_detail_returns_total_and_question_scores(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            responses_path = root / "responses.csv"
            _write_rows(responses_path)
            questions_path = root / "questions.csv"
            with questions_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"])
                writer.writerow(["Q1", "1", "", "1", "4", ""])
                writer.writerow(["Q2", "2", "", "2", "4", ""])

            deps = self._build_deps(responses_path, questions_path)
            result = exam_student_detail("EX1", deps=deps, student_id="S1")

            self.assertTrue(result.get("ok"))
            self.assertEqual(result["student"]["student_id"], "S1")
            self.assertEqual(result["student"]["total_score"], 7.0)
            self.assertEqual(result["question_count"], 2)

    def test_exam_student_detail_requires_disambiguation_for_duplicate_names(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            responses_path = root / "responses.csv"
            _write_rows(responses_path)
            questions_path = root / "questions.csv"
            with questions_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"])
                writer.writerow(["Q1", "1", "", "1", "4", ""])

            deps = self._build_deps(responses_path, questions_path)
            result = exam_student_detail("EX1", deps=deps, student_name="Alex")

            self.assertEqual(result.get("error"), "multiple_students")
            self.assertTrue(result.get("candidates"))

    def test_exam_question_detail_supports_question_no_lookup(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            responses_path = root / "responses.csv"
            _write_rows(responses_path)
            questions_path = root / "questions.csv"
            with questions_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"])
                writer.writerow(["Q1", "1", "", "1", "4", ""])
                writer.writerow(["Q2", "2", "", "2", "4", ""])

            deps = self._build_deps(responses_path, questions_path)
            result = exam_question_detail("EX1", deps=deps, question_no="1", top_n=1)

            self.assertTrue(result.get("ok"))
            self.assertEqual(result["question"]["question_id"], "Q1")
            self.assertEqual(result["question"]["avg_score"], 3.0)
            self.assertEqual(result["distribution"].get("4"), 1)
            self.assertEqual(len(result["sample_top_students"]), 1)
            self.assertEqual(len(result["sample_bottom_students"]), 1)


if __name__ == "__main__":
    unittest.main()
