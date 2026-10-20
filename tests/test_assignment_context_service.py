import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_context_service import (
    build_assignment_context,
    build_bound_student_assignment_extra,
    build_exam_checklist,
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

    def test_load_assignment_stems_rejects_absolute_path_outside_jail(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            secret = root / "tmp" / "secret.md"
            secret.parent.mkdir(parents=True)
            secret.write_text("LEAKED_CONTEXT_STEM", encoding="utf-8")
            _write_questions_csv(
                folder / "questions.csv",
                [
                    {
                        "question_id": "Q1",
                        "kp_id": "kp.x",
                        "difficulty": "basic",
                        "type": "calc",
                        "stem_ref": str(secret),
                        "answer_ref": "",
                        "source": "upload",
                        "tags": "",
                    }
                ],
            )
            items = load_assignment_stems(folder, app_root=root, data_dir=root)
            self.assertEqual(items[0]["stem_text"], "（题干文件缺失）")
            self.assertNotIn("LEAKED_CONTEXT_STEM", json.dumps(items, ensure_ascii=False))

    def test_load_assignment_stems_reads_bank_and_rejects_symlink_escape(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            bank = root / "question_bank" / "stems" / "b1.md"
            bank.parent.mkdir(parents=True)
            bank.write_text("题库可见题干", encoding="utf-8")
            secret = root / "tmp" / "secret.md"
            secret.parent.mkdir(parents=True)
            secret.write_text("LEAKED_SYMLINK", encoding="utf-8")
            link = folder / "stems" / "escape.md"
            link.parent.mkdir(parents=True)
            link.symlink_to(secret)
            _write_questions_csv(
                folder / "questions.csv",
                [
                    {
                        "question_id": "QB",
                        "kp_id": "kp.x",
                        "difficulty": "basic",
                        "type": "calc",
                        "stem_ref": str(bank),
                        "answer_ref": "",
                        "source": "bank",
                        "tags": "",
                    },
                    {
                        "question_id": "QE",
                        "kp_id": "kp.x",
                        "difficulty": "basic",
                        "type": "calc",
                        "stem_ref": str(link),
                        "answer_ref": "",
                        "source": "upload",
                        "tags": "",
                    },
                ],
            )
            items = load_assignment_stems(folder, app_root=root, data_dir=root)
            self.assertEqual(items[0]["stem_text"], "题库可见题干")
            self.assertEqual(items[1]["stem_text"], "（题干文件缺失）")
            self.assertNotIn("LEAKED_SYMLINK", json.dumps(items, ensure_ascii=False))

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

    def test_non_problem_set_join_skips_practice_feedback(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            folder.mkdir(parents=True)
            practice = root / "student_submissions" / "A1" / "S001" / "practice_abc"
            practice.mkdir(parents=True)
            (practice / "meta.json").write_text(
                json.dumps({"status": "submitted", "practice_id": "practice_abc"}),
                encoding="utf-8",
            )
            (practice / "grading_report.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "question_id": "P1",
                                "kp_id": "kp.force",
                                "status": "wrong",
                                "score": 0,
                                "reason": "PRACTICE_FEEDBACK_LEAK",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            detail = {
                "assignment_id": "A1",
                "date": "2026-02-08",
                "meta": {
                    "assignment_kind": "scenario",
                    "content_source": "ai",
                },
                "requirements": {"brief": "只讨论老师 brief。"},
            }
            text = build_bound_student_assignment_extra(
                folder=folder,
                detail=detail,
                data_dir=root,
                app_root=root,
                student_id="S001",
            )
            self.assertIn("只讨论老师 brief。", text)
            self.assertNotIn("PRACTICE_FEEDBACK_LEAK", text)
            self.assertNotIn("【补练短反馈】", text)
            self.assertNotIn("【补练题干】", text)

    def test_exam_checklist_problem_set_uses_stems_not_answers(self):
        stems = [
            {
                "question_id": "Q1",
                "kp_id": "kp.force",
                "stem_text": "可见题干：求加速度。",
                "answer_ref": "answers/q1.md",
                "answer_text": "SECRET_ANSWER_42",
                "expected": "SECRET_EXPECTED",
            }
        ]
        text = build_exam_checklist(
            kind="problem_set",
            stems=stems,
            brief="",
            discussion_goals=[],
            extra_constraints="不许用计算器",
        )
        self.assertIn("【考查清单】", text)
        self.assertIn("一次只问一项", text)
        self.assertIn(
            "1. 考查 Q1（kp=kp.force）：先让学生复述条件，再解释思路。禁止改题干或数值。",
            text,
        )
        self.assertIn("遵守老师限制：不许用计算器", text)
        self.assertNotIn("SECRET_ANSWER_42", text)
        self.assertNotIn("SECRET_EXPECTED", text)
        self.assertNotIn("answer_ref", text)
        self.assertNotIn("讲解依据", text)
        self.assertNotIn("可见题干：求加速度。", text)
        empty = build_exam_checklist(
            kind="problem_set",
            stems=[],
            brief="总要求：牛顿定律",
            discussion_goals=[],
            extra_constraints="",
        )
        self.assertIn("数据块无题干，只根据作业总要求提问", empty)
        self.assertNotIn("总要求：牛顿定律", empty)
        many = build_exam_checklist(
            kind="problem_set",
            stems=[{"question_id": f"Q{i}", "kp_id": "kp.x"} for i in range(1, 11)],
            brief="",
            discussion_goals=[],
            extra_constraints="限" * 250,
        )
        self.assertIn("考查 Q7", many)
        self.assertNotIn("考查 Q8", many)
        self.assertNotIn("考查 Q9", many)
        self.assertIn("遵守老师限制：", many)
        self.assertLessEqual(len(many), 1500)
        item_lines = [line for line in many.splitlines() if line and not line.startswith("【")]
        self.assertLessEqual(len(item_lines), 8)
        for line in item_lines:
            self.assertLessEqual(len(line), 200)

    def test_exam_checklist_scenario_uses_goals_not_new_stems(self):
        text = build_exam_checklist(
            kind="scenario",
            stems=[{"question_id": "Q9", "stem_text": "INVENTED_STEM_SHOULD_NOT_APPEAR"}],
            brief="实验室小车情景正文，不要当学生题干另写。",
            discussion_goals=["说出控制变量", "解释误差来源"],
            extra_constraints="不要另编人物",
        )
        self.assertIn("【考查清单】", text)
        self.assertIn("1. 讨论目标：说出控制变量", text)
        self.assertIn("2. 讨论目标：解释误差来源", text)
        self.assertIn("遵守老师限制：不要另编人物", text)
        self.assertNotIn("INVENTED_STEM_SHOULD_NOT_APPEAR", text)
        self.assertNotIn("讲解依据", text)
        empty = build_exam_checklist(
            kind="scenario",
            stems=[],
            brief="实验室小车",
            discussion_goals=[],
            extra_constraints="",
        )
        self.assertIn("1. 围绕老师 brief 考查理解，不要另编情节。", empty)
        self.assertNotIn("实验室小车", empty)

    def test_exam_checklist_science_history_forbids_invented_dates(self):
        text = build_exam_checklist(
            kind="science_history",
            stems=[],
            brief="牛顿与苹果的课堂材料。",
            discussion_goals=[],
            extra_constraints="",
        )
        self.assertIn("只根据老师材料问因果与概念", text)
        self.assertIn("材料里没写", text)
        self.assertNotIn("1687", text)
        self.assertNotIn("Principia", text)
        with_goals = build_exam_checklist(
            kind="science_history",
            stems=[],
            brief="",
            discussion_goals=["指出材料中的因果关系"],
            extra_constraints="不要补年代",
        )
        self.assertIn("1. 讨论目标：指出材料中的因果关系", with_goals)
        self.assertIn("遵守老师限制：不要补年代", with_goals)

    def test_bound_extra_joins_checklist_after_kind_rules(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            stems_dir = folder / "stems"
            stems_dir.mkdir(parents=True)
            (stems_dir / "q1.md").write_text("可见题干：求合力。", encoding="utf-8")
            _write_questions_csv(
                folder / "questions.csv",
                [
                    {
                        "question_id": "Q1",
                        "kp_id": "kp.force",
                        "difficulty": "basic",
                        "type": "calc",
                        "stem_ref": str(stems_dir / "q1.md"),
                        "answer_ref": "answers/q1.md",
                        "source": "upload",
                        "tags": "",
                    }
                ],
            )
            practice = root / "student_submissions" / "A1" / "S001" / "practice_open"
            practice.mkdir(parents=True)
            (practice / "meta.json").write_text(
                json.dumps({"status": "open", "practice_id": "practice_open"}),
                encoding="utf-8",
            )
            _write_questions_csv(
                practice / "questions.csv",
                [
                    {
                        "question_id": "P1",
                        "kp_id": "kp.force",
                        "difficulty": "basic",
                        "type": "calc",
                        "stem_ref": "",
                        "answer_ref": "",
                        "source": "bank",
                        "tags": "",
                    }
                ],
            )
            detail = {
                "assignment_id": "A1",
                "date": "2026-02-08",
                "question_count": 1,
                "meta": {
                    "assignment_kind": "problem_set",
                    "content_source": "upload",
                },
                "requirements": {"extra_constraints": "不许用计算器"},
            }
            text = build_bound_student_assignment_extra(
                folder=folder,
                detail=detail,
                data_dir=root,
                app_root=root,
                student_id="S001",
            )
            rules_at = text.find("【学习规则】")
            checklist_at = text.find("【考查清单】")
            data_at = text.find("---BEGIN DATA---")
            stems_at = text.find("【作业题干】", data_at)
            practice_at = text.find("【补练题干】", data_at)
            self.assertGreaterEqual(rules_at, 0)
            self.assertGreaterEqual(checklist_at, 0)
            self.assertGreaterEqual(data_at, 0)
            self.assertGreaterEqual(stems_at, 0)
            self.assertLess(rules_at, checklist_at)
            self.assertLess(checklist_at, data_at)
            self.assertLess(data_at, stems_at)
            self.assertIn("额外限制:", text)
            self.assertIn("遵守老师限制：不许用计算器", text)
            self.assertNotIn("讲解依据", text)
            if practice_at >= 0:
                self.assertLess(stems_at, practice_at)
            practical = build_bound_student_assignment_extra(
                folder=folder,
                detail={
                    "assignment_id": "A1",
                    "date": "2026-02-08",
                    "meta": {"assignment_kind": "practical", "content_source": "upload"},
                    "requirements": {"brief": "记录自己的步骤。"},
                },
                data_dir=root,
                app_root=root,
                student_id="S001",
            )
            self.assertLess(practical.find("【学习规则】"), practical.find("【考查清单】"))
            self.assertIn("引导学生描述自己的步骤与现象", practical)
            self.assertIn("提醒提交实践照片", practical)
            self.assertNotIn("【补练题干】", practical)
            self.assertNotIn("【补练短反馈】", practical)

    def test_checklist_excludes_answer_ref(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "A1"
            stems_dir = folder / "stems"
            answers = folder / "answers"
            stems_dir.mkdir(parents=True)
            answers.mkdir(parents=True)
            (stems_dir / "q1.md").write_text("可见题干：求加速度。", encoding="utf-8")
            (answers / "q1.md").write_text("SECRET_ANSWER_42", encoding="utf-8")
            _write_questions_csv(
                folder / "questions.csv",
                [
                    {
                        "question_id": "Q1",
                        "kp_id": "kp.force",
                        "difficulty": "basic",
                        "type": "calc",
                        "stem_ref": str(stems_dir / "q1.md"),
                        "answer_ref": str(answers / "q1.md"),
                        "source": "upload",
                        "tags": "",
                    }
                ],
            )
            text = build_bound_student_assignment_extra(
                folder=folder,
                detail={
                    "assignment_id": "A1",
                    "date": "2026-02-08",
                    "meta": {"assignment_kind": "problem_set", "content_source": "upload"},
                    "requirements": {},
                },
                data_dir=root,
                app_root=root,
                student_id="S001",
            )
            self.assertIn("【考查清单】", text)
            self.assertIn("考查 Q1（kp=kp.force）", text)
            self.assertNotIn("SECRET_ANSWER_42", text)
            self.assertNotIn("answer_ref", text)
            self.assertNotIn("answer_text", text)
            self.assertNotIn("expected", text)


if __name__ == "__main__":
    unittest.main()
