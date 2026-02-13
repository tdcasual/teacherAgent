import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.chat_job_processing_service import ComputeChatReplyDeps, compute_chat_reply_sync


class _Msg:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class _Req:
    def __init__(self, *, assignment_id: str, student_id: str = "S001"):
        self.role = "student"
        self.agent_id = "default"
        self.skill_id = ""
        self.teacher_id = ""
        self.student_id = student_id
        self.assignment_id = assignment_id
        self.assignment_date = "2026-02-08"
        self.persona_id = ""
        self.messages = [_Msg("user", "讲一下牛顿第二定律")]


@contextmanager
def _student_inflight(_student_id):
    yield True


class ChatJobProcessingServiceTest(unittest.TestCase):
    def test_compute_chat_reply_blocks_student_attachment_reference_without_context(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            calls = {"run_agent": 0}
            deps = ComputeChatReplyDeps(
                detect_role=lambda _text: "student",
                diag_log=lambda *_args, **_kwargs: None,
                teacher_assignment_preflight=lambda _req: None,
                resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher"),
                teacher_build_context=lambda *_args, **_kwargs: "",
                detect_student_study_trigger=lambda _text: False,
                load_profile_file=lambda _path: {"student_id": "S001"},
                data_dir=root / "data",
                build_verified_student_context=lambda _sid, _profile: "verified",
                build_assignment_detail_cached=lambda _folder, include_text=False: {"assignment_id": "A1"},
                find_assignment_for_date=lambda *_args, **_kwargs: None,
                parse_date_str=lambda raw: str(raw or ""),
                build_assignment_context=lambda *_args, **_kwargs: "",
                chat_extra_system_max_chars=6000,
                trim_messages=lambda msgs, role_hint=None: msgs,
                student_inflight=_student_inflight,
                run_agent=lambda *_args, **_kwargs: calls.update({"run_agent": calls["run_agent"] + 1}) or {"reply": "OK"},
                normalize_math_delimiters=lambda text: text,
                resolve_effective_skill=lambda _role, _skill_id, _last_user_text: {},
                resolve_student_persona_runtime=lambda _sid, _pid: {},
            )
            req = _Req(assignment_id="")
            req.messages = [_Msg("user", "给出这个文件中所有人的成绩")]
            reply, role_hint, last_user = compute_chat_reply_sync(req, deps=deps)
            self.assertIn("没有可读取的附件上下文", reply)
            self.assertEqual(role_hint, "student")
            self.assertEqual(last_user, "给出这个文件中所有人的成绩")
            self.assertEqual(calls["run_agent"], 0)

    def test_compute_chat_reply_ignores_invalid_assignment_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            calls = {"build_assignment_detail": 0}
            deps = ComputeChatReplyDeps(
                detect_role=lambda _text: "student",
                diag_log=lambda *_args, **_kwargs: None,
                teacher_assignment_preflight=lambda _req: None,
                resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher"),
                teacher_build_context=lambda *_args, **_kwargs: "",
                detect_student_study_trigger=lambda _text: False,
                load_profile_file=lambda _path: {"student_id": "S001"},
                data_dir=root / "data",
                build_verified_student_context=lambda _sid, _profile: "verified",
                build_assignment_detail_cached=lambda _folder, include_text=False: calls.update(
                    {"build_assignment_detail": calls["build_assignment_detail"] + 1}
                )
                or {"assignment_id": "A1"},
                find_assignment_for_date=lambda *_args, **_kwargs: None,
                parse_date_str=lambda raw: str(raw or ""),
                build_assignment_context=lambda *_args, **_kwargs: "",
                chat_extra_system_max_chars=6000,
                trim_messages=lambda msgs, role_hint=None: msgs,
                student_inflight=_student_inflight,
                run_agent=lambda *_args, **_kwargs: {"reply": "OK"},
                normalize_math_delimiters=lambda text: text,
                resolve_effective_skill=lambda _role, _skill_id, _last_user_text: {},
                resolve_student_persona_runtime=lambda _sid, _pid: {},
            )
            req = _Req(assignment_id="../escape")
            reply, role_hint, last_user = compute_chat_reply_sync(req, deps=deps)
            self.assertEqual(reply, "OK")
            self.assertEqual(role_hint, "student")
            self.assertEqual(last_user, "讲一下牛顿第二定律")
            self.assertEqual(calls["build_assignment_detail"], 0)

    def test_compute_chat_reply_ignores_invalid_student_profile_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            calls = {"load_profile": 0}
            deps = ComputeChatReplyDeps(
                detect_role=lambda _text: "student",
                diag_log=lambda *_args, **_kwargs: None,
                teacher_assignment_preflight=lambda _req: None,
                resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher"),
                teacher_build_context=lambda *_args, **_kwargs: "",
                detect_student_study_trigger=lambda _text: False,
                load_profile_file=lambda _path: calls.update({"load_profile": calls["load_profile"] + 1}) or {"student_id": "S001"},
                data_dir=root / "data",
                build_verified_student_context=lambda _sid, _profile: "verified",
                build_assignment_detail_cached=lambda _folder, include_text=False: {"assignment_id": "A1"},
                find_assignment_for_date=lambda *_args, **_kwargs: None,
                parse_date_str=lambda raw: str(raw or ""),
                build_assignment_context=lambda *_args, **_kwargs: "",
                chat_extra_system_max_chars=6000,
                trim_messages=lambda msgs, role_hint=None: msgs,
                student_inflight=_student_inflight,
                run_agent=lambda *_args, **_kwargs: {"reply": "OK"},
                normalize_math_delimiters=lambda text: text,
                resolve_effective_skill=lambda _role, _skill_id, _last_user_text: {},
                resolve_student_persona_runtime=lambda _sid, _pid: {},
            )
            req = _Req(assignment_id="", student_id="../escape")
            reply, role_hint, last_user = compute_chat_reply_sync(req, deps=deps)
            self.assertEqual(reply, "OK")
            self.assertEqual(role_hint, "student")
            self.assertEqual(last_user, "讲一下牛顿第二定律")
            self.assertEqual(calls["load_profile"], 0)

    def test_compute_chat_reply_applies_persona_prompt_and_first_notice(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured_extra_system = {"value": ""}

            def _run_agent(_messages, _role_hint, *, extra_system=None, **_kwargs):
                captured_extra_system["value"] = str(extra_system or "")
                return {"reply": "OK"}

            deps = ComputeChatReplyDeps(
                detect_role=lambda _text: "student",
                diag_log=lambda *_args, **_kwargs: None,
                teacher_assignment_preflight=lambda _req: None,
                resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher"),
                teacher_build_context=lambda *_args, **_kwargs: "",
                detect_student_study_trigger=lambda _text: False,
                load_profile_file=lambda _path: {"student_id": "S001"},
                data_dir=root / "data",
                build_verified_student_context=lambda _sid, _profile: "verified",
                build_assignment_detail_cached=lambda _folder, include_text=False: {"assignment_id": "A1"},
                find_assignment_for_date=lambda *_args, **_kwargs: None,
                parse_date_str=lambda raw: str(raw or ""),
                build_assignment_context=lambda *_args, **_kwargs: "",
                chat_extra_system_max_chars=6000,
                trim_messages=lambda msgs, role_hint=None: msgs,
                student_inflight=_student_inflight,
                run_agent=_run_agent,
                normalize_math_delimiters=lambda text: text,
                resolve_effective_skill=lambda _role, _skill_id, _last_user_text: {},
                resolve_student_persona_runtime=lambda _sid, _pid: {
                    "ok": True,
                    "persona_prompt": "persona-style-prompt",
                    "first_notice": True,
                    "persona_name": "林黛玉风格",
                },
            )
            req = _Req(assignment_id="")
            req.persona_id = "preset_1"
            reply, role_hint, last_user = compute_chat_reply_sync(req, deps=deps)
            self.assertTrue(reply.startswith("提示：你当前使用的是「林黛玉风格」虚拟风格卡"))
            self.assertIn("OK", reply)
            self.assertEqual(role_hint, "student")
            self.assertEqual(last_user, "讲一下牛顿第二定律")
            self.assertIn("persona-style-prompt", captured_extra_system["value"])


if __name__ == "__main__":
    unittest.main()
