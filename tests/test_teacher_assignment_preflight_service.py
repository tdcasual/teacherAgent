import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from services.api.teacher_assignment_preflight_service import (
    TeacherAssignmentPreflightDeps,
    teacher_assignment_preflight,
    teacher_workflow_preflight_reply,
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
    def _deps(
        self,
        analysis: Optional[Dict[str, Any]],
        allow_tools=("assignment.generate", "assignment.requirements.save"),
    ):
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
            if not str(args.get("subject_id") or "").strip():
                return {"error": "subject_id_required"}
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

    def test_missing_small_rewrites_full_template_to_incremental_prompt(self):
        full_template = (
            "老师您好，已识别到您要布置关于“运动的合成与分解”的作业，日期为2026-02-12。\n\n"
            "为了生成一份高质量的作业，请您补充以下信息（共8项）：\n"
            "1. 学科\n2. 年级\n3. 班级水平\n4. 核心概念\n5. 典型问题\n6. 常见误解\n7. 作业时长\n8. 作业偏好\n\n"
            "请按此模板回复，我将为您生成完整的作业。"
        )
        analysis = {
            "intent": "assignment",
            "assignment_id": "A1",
            "date": "2026-02-07",
            "missing": ["常见误解不足4个"],
            "next_prompt": full_template,
        }
        deps, _logs, _saved, generated = self._deps(analysis=analysis)
        req = _Req(messages=[_Msg(role="user", content="作业信息已给你大部分，请继续")])
        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("请仅补充以下内容", result)
        self.assertIn("常见误解不足4个", result)
        self.assertNotIn("共8项", result)
        self.assertEqual(generated, [])

    def test_missing_large_keeps_full_template_prompt(self):
        full_template = (
            "老师您好！为了生成一份高质量的作业，请您提供以下信息：\n"
            "1. 学科\n2. 年级\n3. 班级水平\n4. 核心概念\n5. 典型问题\n6. 常见误解\n7. 作业时长\n8. 作业偏好"
        )
        analysis = {
            "intent": "assignment",
            "assignment_id": "",
            "date": "",
            "missing": ["作业ID", "学科", "年级", "班级水平", "核心概念", "典型问题"],
            "next_prompt": full_template,
        }
        deps, _logs, _saved, generated = self._deps(analysis=analysis)
        req = _Req(messages=[_Msg(role="user", content="生成作业")])
        result = teacher_assignment_preflight(req, deps=deps)
        self.assertEqual(result, full_template)
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
        self.assertIn("作业草稿已写入：A1", result)
        self.assertIn("draft", result)
        self.assertEqual(len(saved), 1)
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0]["assignment_id"], "A1")
        self.assertEqual(generated[0]["subject_id"], "physics")

    def test_generate_surfaces_subject_id_required_when_missing(self):
        analysis = {
            "intent": "assignment",
            "assignment_id": "A1",
            "date": "2026-02-07",
            "missing": [],
            "ready_to_generate": True,
            "kp_list": ["牛顿定律"],
            "mode": "kp",
        }
        deps, logs, _saved, generated = self._deps(analysis=analysis)
        req = _Req(messages=[_Msg(role="user", content="请生成今天作业")], skill_id="default")
        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("subject_id_required", result)
        self.assertEqual(generated[0]["subject_id"], "")
        self.assertTrue(any(event == "teacher_preflight.generate_error" for event, _ in logs))

    def test_returns_disabled_message_when_tools_not_allowed(self):
        analysis = {
            "intent": "assignment",
            "assignment_id": "A1",
            "date": "2026-02-07",
            "missing": [],
            "ready_to_generate": True,
        }
        deps, _logs, _saved, generated = self._deps(
            analysis=analysis, allow_tools=("assignment.generate",)
        )
        req = _Req(messages=[_Msg(role="user", content="请生成作业")], skill_id="default")
        result = teacher_assignment_preflight(req, deps=deps)
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("未开启作业生成功能", result)
        self.assertEqual(generated, [])

    def test_student_focus_workflow_requires_specific_student_when_reference_is_ambiguous(self):
        deps, _logs, _saved, _generated = self._deps(analysis=None)
        req = _Req(
            messages=[_Msg(role="user", content="请分析这个学生最近为什么掉分")],
            skill_id="physics-student-focus",
        )

        result = teacher_workflow_preflight_reply(
            req,
            effective_skill_id="physics-student-focus",
            last_user_text="请分析这个学生最近为什么掉分",
            attachment_context="",
            deps=deps,
        )

        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("学生", result)
        self.assertIn("姓名", result)

    def test_lesson_capture_workflow_requires_attachment_or_lesson_id(self):
        deps, _logs, _saved, _generated = self._deps(analysis=None)
        req = _Req(
            messages=[_Msg(role="user", content="把这节课的板书整理成讲义")],
            skill_id="physics-lesson-capture",
        )

        result = teacher_workflow_preflight_reply(
            req,
            effective_skill_id="physics-lesson-capture",
            last_user_text="把这节课的板书整理成讲义",
            attachment_context="",
            deps=deps,
        )

        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("上传", result)
        self.assertIn("课堂材料", result)


if __name__ == "__main__":
    unittest.main()
