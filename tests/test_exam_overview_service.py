import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_overview_service import (
    ExamOverviewDeps,
    exam_analysis_get,
    exam_get,
    exam_students_list,
)


class ExamOverviewServiceTest(unittest.TestCase):
    def _deps(self, root: Path, parse_xlsx_with_script=None):
        def _load_exam_manifest(exam_id: str):
            manifest_path = root / "data" / "exams" / exam_id / "manifest.json"
            if not manifest_path.exists():
                return None
            return json.loads(manifest_path.read_text(encoding="utf-8"))

        def _exam_responses_path(manifest):
            path = manifest.get("responses")
            return Path(path) if path else None

        def _exam_questions_path(manifest):
            path = manifest.get("questions")
            return Path(path) if path else None

        def _exam_analysis_draft_path(manifest):
            path = manifest.get("analysis")
            return Path(path) if path else None

        def _read_questions_csv(path: Path):
            lines = path.read_text(encoding="utf-8").splitlines()
            out = {}
            for idx, line in enumerate(lines[1:], start=1):
                qid = line.split(",", 1)[0].strip()
                if qid:
                    out[qid] = {"question_id": qid, "question_no": str(idx)}
            return out

        def _compute_exam_totals(path: Path):
            rows = path.read_text(encoding="utf-8").splitlines()[1:]
            totals = {}
            students = {}
            for row in rows:
                student_id, student_name, class_name, score = row.split(",")
                score_val = float(score)
                totals[student_id] = totals.get(student_id, 0.0) + score_val
                students[student_id] = {
                    "student_id": student_id,
                    "student_name": student_name,
                    "class_name": class_name,
                }
            return {"totals": totals, "students": students}

        return ExamOverviewDeps(
            data_dir=root / "data",
            load_exam_manifest=_load_exam_manifest,
            exam_responses_path=_exam_responses_path,
            exam_questions_path=_exam_questions_path,
            exam_analysis_draft_path=_exam_analysis_draft_path,
            read_questions_csv=_read_questions_csv,
            compute_exam_totals=_compute_exam_totals,
            now_iso=lambda: "2026-02-08T12:00:00",
            parse_xlsx_with_script=parse_xlsx_with_script,
        )

    def _write_manifest_bundle(self, root: Path, exam_id: str):
        exam_dir = root / "data" / "exams" / exam_id
        exam_dir.mkdir(parents=True, exist_ok=True)
        responses = exam_dir / "responses.csv"
        questions = exam_dir / "questions.csv"
        analysis = exam_dir / "analysis.json"
        responses.write_text(
            "student_id,student_name,class_name,score\nS1,张三,高二2403班,80\nS2,李四,高二2403班,60\n",
            encoding="utf-8",
        )
        questions.write_text("question_id,max_score\nQ1,100\n", encoding="utf-8")
        manifest = {
            "exam_id": exam_id,
            "generated_at": "2026-02-08T09:00:00",
            "meta": {"score_mode": "question"},
            "responses": str(responses),
            "questions": str(questions),
            "analysis": str(analysis),
        }
        (exam_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return analysis

    def test_exam_get_and_students_list(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_manifest_bundle(root, "EX1")
            deps = self._deps(root)

            summary = exam_get("EX1", deps)
            listing = exam_students_list("EX1", 10, deps)

            self.assertTrue(summary.get("ok"))
            self.assertEqual(summary.get("counts", {}).get("students"), 2)
            self.assertTrue(listing.get("ok"))
            self.assertEqual(listing.get("students", [])[0].get("student_id"), "S1")

    def test_exam_analysis_prefers_draft_and_falls_back_to_computed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            analysis_path = self._write_manifest_bundle(root, "EX1")
            deps = self._deps(root)

            analysis_path.write_text('{"notes":"precomputed"}', encoding="utf-8")
            from_draft = exam_analysis_get("EX1", deps)
            self.assertEqual(from_draft.get("analysis", {}).get("notes"), "precomputed")

            analysis_path.unlink()
            computed = exam_analysis_get("EX1", deps)
            self.assertEqual(computed.get("source"), "computed")
            self.assertEqual(computed.get("analysis", {}).get("totals", {}).get("student_count"), 2)


    def test_exam_get_total_mode_falls_back_to_subject_scores_from_xlsx(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            exam_id = "EX20260209_9b92e1"
            exam_dir = root / "data" / "exams" / exam_id
            exam_dir.mkdir(parents=True, exist_ok=True)

            responses = exam_dir / "responses.csv"
            responses.write_text(
                "student_id,student_name,class_name,score\nS1,张三,高二2403班,500\nS2,李四,高二2403班,420\n",
                encoding="utf-8",
            )
            questions = exam_dir / "questions.csv"
            questions.write_text("question_id,max_score\nTOTAL,750\n", encoding="utf-8")
            scores_dir = exam_dir / "scores"
            scores_dir.mkdir(parents=True, exist_ok=True)
            (scores_dir / "scores.xlsx").write_bytes(b"xlsx")

            manifest = {
                "exam_id": exam_id,
                "generated_at": "2026-02-08T09:00:00",
                "meta": {"score_mode": "total", "class_name": "高二2403班"},
                "responses": str(responses),
                "questions": str(questions),
            }
            (exam_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

            def _fake_parse_xlsx_with_script(_xlsx, _out, _exam_id, _class_name, _subject_candidate_id=None):
                return [
                    {
                        "exam_id": _exam_id,
                        "student_id": "S1",
                        "student_name": "张三",
                        "class_name": "高二2403班",
                        "question_id": "SUBJECT_PHYSICS",
                        "question_no": "",
                        "sub_no": "",
                        "raw_label": "物理",
                        "raw_value": "88",
                        "raw_answer": "",
                        "score": 88.0,
                    },
                    {
                        "exam_id": _exam_id,
                        "student_id": "S2",
                        "student_name": "李四",
                        "class_name": "高二2403班",
                        "question_id": "SUBJECT_PHYSICS",
                        "question_no": "",
                        "sub_no": "",
                        "raw_label": "物理",
                        "raw_value": "72.5",
                        "raw_answer": "",
                        "score": 72.5,
                    },
                ], {"mode": "subject"}

            deps = self._deps(root, parse_xlsx_with_script=_fake_parse_xlsx_with_script)
            summary = exam_get(exam_id, deps)
            listing = exam_students_list(exam_id, 10, deps)
            analysis = exam_analysis_get(exam_id, deps)

            self.assertTrue(summary.get("ok"))
            self.assertEqual(summary.get("score_mode"), "subject")
            self.assertEqual(summary.get("score_mode_source"), "subject_from_scores_file")
            self.assertEqual((summary.get("meta") or {}).get("score_mode_original"), "total")
            self.assertEqual(summary.get("counts", {}).get("students"), 2)

            self.assertTrue(listing.get("ok"))
            self.assertEqual(listing.get("students", [])[0].get("student_id"), "S1")
            self.assertEqual(listing.get("students", [])[0].get("total_score"), 88.0)

            self.assertTrue(analysis.get("ok"))
            self.assertEqual(analysis.get("source"), "computed_subject_from_scores")
            self.assertEqual((analysis.get("analysis") or {}).get("question_metrics", [{}])[0].get("question_id"), "SUBJECT_PHYSICS")


if __name__ == "__main__":
    unittest.main()
