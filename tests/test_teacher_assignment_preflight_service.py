import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from services.api.teacher_assignment_preflight_service import (
    TeacherAssignmentPreflightDeps,
    teacher_assignment_preflight,
)


@dataclass
class _Msg:
    role: str
    content: str


@dataclass
class _Req:
    messages: list
    assignment_id: Optional[str] = None
    assignment_date: Optional[str] = None
    skill_id: Optional[str] = None


class TeacherAssignmentPreflightServiceTest(unittest.TestCase):
    def _deps(self, analysis: Optional[Dict[str, Any]], allow_tools=("assignment.generate", "assignment.requirements.save")):
        logs = []
        saved = []
        generated = []

        def _diag(event: str, payload: Dict[str, Any]):
            logs.append((event, payload))

        def _save(*args, **kwargs):
            saved.append((args, kwargs))
            return {"ok": True}

        def _gen(args: Dict[str, Any]):
            generated.append(args)
            return {"ok": True, "output": "ok"}

        deps = TeacherAssignmentPreflightDeps(
            app_root=Path("/tmp/app"),
            detect_assignment_intent=lambda text: "作业" in (text or ""),
            llm_assignment_gate=lambda _req: analysis,
            diag_log=_diag,
            allowed_tools=lambda _role: list(allow_tools),
            parse_date_str=lambda value: str(value or "2026-02-07"),
            today_iso=lambda: "2026-02-07",
            format_requirements_prompt=lambda **kwargs: f"PROMPT:{kwargs.get('errors')}",
            save_assignment_requirements=_save,
            assignment_generate=_gen,
            extract_exam_id=lambda text: "EX20260209_9b92e1" if "EX20260209_9b92e1" in (text or "") else None,
            exam_get=lambda _exam_id: {},
        )
        return deps, logs, saved, generated

    def test_returns_none_when_no_assignment_intent(self):
        deps, logs, _saved, _generated = self._deps(analysis=None)
        req = _Req(messages=[_Msg(role="user", content="你好")])
        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsNone(result)
        self.assertTrue(any(event == "teacher_preflight.skip" for event, _ in logs))

    def test_returns_prompt_when_missing_fields(self):
        analysis = {
            "intent": "assignment",
            "assignment_id": "A1",
            "date": "2026-02-07",
            "missing": ["知识点"],
            "next_prompt": "请补充知识点",
        }
        deps, _logs, _saved, generated = self._deps(analysis=analysis)
        req = _Req(messages=[_Msg(role="user", content="请帮我生成作业")])
        result = teacher_assignment_preflight(req, deps=deps)
        self.assertEqual(result, "请补充知识点")
        self.assertEqual(generated, [])

    def test_generates_assignment_when_ready(self):
        analysis = {
            "intent": "assignment",
            "assignment_id": "A1",
            "date": "2026-02-07",
            "missing": [],
            "ready_to_generate": True,
            "kp_list": ["牛顿定律"],
            "question_ids": [],
            "per_kp": 5,
            "mode": "kp",
            "requirements": {"subject": "物理"},
        }
        deps, _logs, saved, generated = self._deps(analysis=analysis)
        req = _Req(messages=[_Msg(role="user", content="请生成今天作业")], skill_id="default")
        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("作业已生成：A1", result)
        self.assertEqual(len(saved), 1)
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0]["assignment_id"], "A1")

    def test_returns_disabled_message_when_tools_not_allowed(self):
        analysis = {
            "intent": "assignment",
            "assignment_id": "A1",
            "date": "2026-02-07",
            "missing": [],
            "ready_to_generate": True,
        }
        deps, _logs, _saved, generated = self._deps(analysis=analysis, allow_tools=("assignment.generate",))
        req = _Req(messages=[_Msg(role="user", content="请生成作业")], skill_id="default")
        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("未开启作业生成功能", result)
        self.assertEqual(generated, [])

    def test_subject_score_request_on_total_mode_is_guarded(self):
        deps, logs, _saved, generated = self._deps(analysis=None)
        deps = TeacherAssignmentPreflightDeps(
            **{
                **deps.__dict__,
                "exam_get": lambda _exam_id: {
                    "ok": True,
                    "exam_id": "EX20260209_9b92e1",
                    "score_mode": "total",
                    "totals_summary": {
                        "avg_total": 371.714,
                        "median_total": 366.5,
                        "max_total_observed": 511.5,
                        "min_total_observed": 289.5,
                    },
                },
            }
        )
        req = _Req(
            messages=[
                _Msg(role="assistant", content="上一轮回复"),
                _Msg(role="user", content="分析EX20260209_9b92e1的物理成绩"),
            ],
            skill_id="default",
        )

        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("单科成绩说明", result)
        self.assertIn("score_mode: \"total\"", result)
        self.assertIn("不能把总分当作物理单科成绩", result)
        self.assertEqual(generated, [])
        self.assertTrue(any(event == "teacher_preflight.subject_total_guard" for event, _ in logs))

    def test_subject_score_request_not_blocked_for_non_total_mode(self):
        deps, logs, _saved, generated = self._deps(analysis=None)
        deps = TeacherAssignmentPreflightDeps(
            **{
                **deps.__dict__,
                "exam_get": lambda _exam_id: {
                    "ok": True,
                    "exam_id": "EX20260209_9b92e1",
                    "score_mode": "subject",
                },
            }
        )
        req = _Req(
            messages=[
                _Msg(role="user", content="分析EX20260209_9b92e1的物理成绩"),
            ],
            skill_id="default",
        )

        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsNone(result)
        self.assertEqual(generated, [])
        self.assertFalse(any(event == "teacher_preflight.subject_total_guard" for event, _ in logs))

    def test_subject_score_request_on_total_mode_allows_matching_single_subject_exam(self):
        deps, logs, _saved, generated = self._deps(analysis=None)
        deps = TeacherAssignmentPreflightDeps(
            **{
                **deps.__dict__,
                "exam_get": lambda _exam_id: {
                    "ok": True,
                    "exam_id": "EX20260209_9b92e1",
                    "score_mode": "total",
                    "meta": {"subject": "physics"},
                    "totals_summary": {
                        "avg_total": 371.714,
                        "median_total": 366.5,
                        "max_total_observed": 511.5,
                        "min_total_observed": 289.5,
                    },
                },
            }
        )
        req = _Req(
            messages=[
                _Msg(role="user", content="分析EX20260209_9b92e1的物理成绩"),
            ],
            skill_id="default",
        )

        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsNone(result)
        self.assertEqual(generated, [])
        self.assertFalse(any(event == "teacher_preflight.subject_total_guard" for event, _ in logs))
        self.assertTrue(any(event == "teacher_preflight.subject_total_allow_single_subject" for event, _ in logs))


if __name__ == "__main__":
    unittest.main()
