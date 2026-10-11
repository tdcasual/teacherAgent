import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_context_service import (
    build_assignment_context,
    build_kind_coach_rules,
    load_assignment_stems,
    load_latest_practice_short_feedback,
    load_open_practice_stems,
)

AUTHORING = ("进入诊断问题", "【诊断问题】", "动态生成Q1", "列出考试", "考试分析")


def _write_questions_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "question_id",
        "kp_id",
        "difficulty",
        "type",
        "stem_ref",
        "answer_ref",
        "source",
        "tags",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


class AssignmentContextServiceTest(unittest.TestCase):
    def test_returns_none_when_detail_missing(self):
        self.assertIsNone(build_assignment_context(None))

    def test_non_study_mode_contains_data_block(self):
        detail = {
            "assignment_id": "A1",
            "date": "2026-02-07",
            "question_count": 5,
            "meta": {
                "mode": "upload",
                "target_kp": ["牛顿定律"],
                "assignment_kind": "problem_set",
                "content_source": "upload",
            },
            "requirements": {},
        }
        result = build_assignment_context(detail, study_mode=False)
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("---BEGIN DATA---", result)
        self.assertIn("Assignment ID: A1", result)
        self.assertIn("assignment_kind=problem_set", result)
        self.assertIn("content_source=upload", result)
        self.assertNotIn("【学习与诊断规则", result)
        self.assertNotIn("动态生成Q1", result)

    def test_study_mode_does_not_require_discussion_marker(self):
        detail = {
            "assignment_id": "A1",
            "date": "2026-02-07",
            "question_count": 5,
            "meta": {"mode": "upload", "target_kp": ["牛顿定律"]},
            "requirements": {"subject": "物理", "topic": "力学", "brief": "只讨论牛顿定律"},
        }
        marker = "【个性化作业】"
        result = build_assignment_context(
            detail, study_mode=True, discussion_complete_marker=marker
        )
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertNotIn("【学习与诊断规则", result)
        self.assertNotIn(marker, result)
        self.assertNotIn("K0)", result)
        self.assertNotIn("K) 个性化作业生成", result)
        self.assertIn("作业总要求", result)
        self.assertIn("只讨论牛顿定律", result)
        for phrase in AUTHORING:
            self.assertNotIn(phrase, result)

    def test_stems_block_excludes_answer_fields(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            stems = folder / "stems"
            answers = folder / "answers"
            stems.mkdir(parents=True)
            answers.mkdir(parents=True)
            (stems / "q1.md").write_text("可见题干：求加速度。", encoding="utf-8")
            (answers / "q1.md").write_text("SECRET_ANSWER_42", encoding="utf-8")
            _write_questions_csv(
                folder / "questions.csv",
                [
                    {
                        "question_id": "Q1",
                        "kp_id": "kp.force",
                        "difficulty": "basic",
                        "type": "calc",
                        "stem_ref": str(stems / "q1.md"),
                        "answer_ref": str(answers / "q1.md"),
                        "source": "upload",
                        "tags": "",
                    }
                ],
            )
            items = load_assignment_stems(folder, app_root=root, limit=8)
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item["question_id"], "Q1")
            self.assertEqual(item["kp_id"], "kp.force")
            self.assertEqual(item["difficulty"], "basic")
            self.assertEqual(item["stem_text"], "可见题干：求加速度。")
            self.assertNotIn("answer_ref", item)
            self.assertNotIn("answer_text", item)
            self.assertNotIn("expected", item)
            dumped = json.dumps(item, ensure_ascii=False)
            self.assertNotIn("SECRET_ANSWER_42", dumped)
            self.assertNotIn("answer_ref", dumped)

    def test_missing_stem_file_uses_placeholder(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            _write_questions_csv(
                folder / "questions.csv",
                [
                    {
                        "question_id": "Q9",
                        "kp_id": "kp.x",
                        "difficulty": "medium",
                        "type": "calc",
                        "stem_ref": "stems/missing.md",
                        "answer_ref": "answers/missing.md",
                        "source": "upload",
                        "tags": "",
                    }
                ],
            )
            items = load_assignment_stems(folder, app_root=root)
            self.assertEqual(items[0]["stem_text"], "（题干文件缺失）")
            self.assertNotIn("answer_ref", items[0])

    def test_science_history_rules_forbid_invented_story(self):
        text = build_kind_coach_rules("science_history")
        self.assertIn("不要补一段历史故事", text)
        self.assertIn("【学习规则】", text)
        for phrase in AUTHORING:
            self.assertNotIn(phrase, text)

    def test_scenario_kind_rules_omit_practice_authoring(self):
        text = build_kind_coach_rules("scenario")
        self.assertIn("只围绕老师 brief", text)
        self.assertNotIn("补练题", text)
        for phrase in AUTHORING:
            self.assertNotIn(phrase, text)

    def test_open_practice_stems_may_return_empty(self):
        with TemporaryDirectory() as td:
            rows = load_open_practice_stems(
                Path(td),
                assignment_id="A1",
                student_id="S001",
                app_root=Path(td),
            )
            self.assertEqual(rows, [])

    def test_latest_practice_feedback_skips_answers(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            practice = root / "student_submissions" / "A1" / "S001" / "practice_abc"
            practice.mkdir(parents=True)
            (practice / "meta.json").write_text(
                json.dumps({"status": "submitted", "practice_id": "practice_abc"}),
                encoding="utf-8",
            )
            (practice / "feedback.md").write_text("LEAK_FEEDBACK_MD", encoding="utf-8")
            (practice / "grading_report.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "question_id": "P1",
                                "kp_id": "kp.force",
                                "status": "wrong",
                                "score": 0,
                                "reason": "单位错了",
                                "expected": "SECRET_EXPECTED",
                                "answer_ref": "answers/p1.md",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            text = load_latest_practice_short_feedback(
                root, assignment_id="A1", student_id="S001"
            )
            self.assertIn("P1", text)
            self.assertIn("单位错了", text)
            self.assertNotIn("SECRET_EXPECTED", text)
            self.assertNotIn("answer_ref", text)
            self.assertNotIn("LEAK_FEEDBACK_MD", text)


if __name__ == "__main__":
    unittest.main()
