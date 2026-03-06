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
        self.skill_id = ""
        self.teacher_id = ""
        self.student_id = student_id
        self.assignment_id = assignment_id
        self.assignment_date = "2026-02-08"
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
            )
            req = _Req(assignment_id="", student_id="../escape")
            reply, role_hint, last_user = compute_chat_reply_sync(req, deps=deps)
            self.assertEqual(reply, "OK")
            self.assertEqual(role_hint, "student")
            self.assertEqual(last_user, "讲一下牛顿第二定律")
            self.assertEqual(calls["load_profile"], 0)

    def test_compute_chat_reply_internal_type_error_does_not_retry_event_sink_fallback(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            run_calls = {"count": 0}

            def _run_agent(*_args, **_kwargs):
                run_calls["count"] += 1
                raise TypeError("internal_run_agent_type_error")

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
            )
            req = _Req(assignment_id="")
            with self.assertRaises(TypeError):
                compute_chat_reply_sync(
                    req,
                    deps=deps,
                    event_sink=lambda *_args, **_kwargs: None,
                )
            self.assertEqual(run_calls["count"], 1)

    def test_compute_chat_reply_signature_like_internal_type_error_does_not_retry_event_sink_fallback(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            run_calls = {"count": 0}

            def _run_agent(*_args, **_kwargs):
                run_calls["count"] += 1
                raise TypeError("helper() missing 1 required positional argument: 'ctx'")

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
            )
            req = _Req(assignment_id="")
            with self.assertRaises(TypeError):
                compute_chat_reply_sync(
                    req,
                    deps=deps,
                    event_sink=lambda *_args, **_kwargs: None,
                )
            self.assertEqual(run_calls["count"], 1)

    def test_compute_chat_reply_uninspectable_signature_like_internal_type_error_does_not_retry(
        self,
    ):
        with TemporaryDirectory() as td:
            root = Path(td)
            run_calls = {"count": 0}

            class _RunAgent:
                @property
                def __signature__(self):
                    raise ValueError("signature unavailable")

                def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                    run_calls["count"] += 1
                    raise TypeError("helper() missing 1 required positional argument: 'ctx'")

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
                run_agent=_RunAgent(),
                normalize_math_delimiters=lambda text: text,
                resolve_effective_skill=lambda _role, _skill_id, _last_user_text: {},
            )
            req = _Req(assignment_id="")
            with self.assertRaises(TypeError):
                compute_chat_reply_sync(
                    req,
                    deps=deps,
                    event_sink=lambda *_args, **_kwargs: None,
                )
            self.assertEqual(run_calls["count"], 1)

    def test_compute_chat_reply_rejects_legacy_run_agent_without_event_sink(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            run_calls = {"count": 0}

            def _run_agent(_messages, _role_hint, *, extra_system=None, skill_id=None, teacher_id=None):
                del _messages, _role_hint, extra_system, skill_id, teacher_id
                run_calls["count"] += 1
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
            )
            req = _Req(assignment_id="")
            with self.assertRaises(TypeError):
                compute_chat_reply_sync(
                    req,
                    deps=deps,
                    event_sink=lambda *_args, **_kwargs: None,
                )
            # Strict keyword call binding fails before entering the legacy callable.
            self.assertEqual(run_calls["count"], 0)


class _TeacherReq:
    def __init__(self, text: str):
        self.role = "teacher"
        self.skill_id = ""
        self.teacher_id = "teacher-1"
        self.student_id = ""
        self.assignment_id = ""
        self.assignment_date = None
        self.attachment_context = ""
        self.messages = [_Msg("user", text)]


class TeacherWorkflowResolutionTest(unittest.TestCase):
    def test_compute_chat_reply_emits_workflow_resolution_event_for_teacher(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured = {"skill_id": None, "teacher_id": None, "extra_system": None}
            events = []

            def _run_agent(messages, role_hint, *, extra_system=None, skill_id=None, teacher_id=None, event_sink=None):
                del messages, role_hint, event_sink
                captured["skill_id"] = skill_id
                captured["teacher_id"] = teacher_id
                captured["extra_system"] = extra_system
                return {"reply": "OK"}

            deps = ComputeChatReplyDeps(
                detect_role=lambda _text: "teacher",
                diag_log=lambda *_args, **_kwargs: None,
                teacher_assignment_preflight=lambda _req: None,
                resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher-1"),
                teacher_build_context=lambda *_args, **_kwargs: "teacher-context",
                detect_student_study_trigger=lambda _text: False,
                load_profile_file=lambda _path: {},
                data_dir=root / "data",
                build_verified_student_context=lambda _sid, _profile: "",
                build_assignment_detail_cached=lambda *_args, **_kwargs: {},
                find_assignment_for_date=lambda *_args, **_kwargs: None,
                parse_date_str=lambda raw: str(raw or ""),
                build_assignment_context=lambda *_args, **_kwargs: "",
                chat_extra_system_max_chars=6000,
                trim_messages=lambda msgs, role_hint=None: msgs,
                student_inflight=_student_inflight,
                run_agent=_run_agent,
                normalize_math_delimiters=lambda text: text,
                resolve_effective_skill=lambda _role, _skill_id, _last_user_text: {
                    "requested_skill_id": "",
                    "effective_skill_id": "physics-homework-generator",
                    "reason": "auto_rule",
                    "confidence": 0.64,
                    "candidates": [{"skill_id": "physics-homework-generator", "score": 12}],
                },
            )

            reply, role_hint, last_user = compute_chat_reply_sync(
                _TeacherReq("请帮我生成作业"),
                deps=deps,
                event_sink=lambda event_type, payload: events.append((event_type, payload)),
            )

            self.assertEqual(reply, "OK")
            self.assertEqual(role_hint, "teacher")
            self.assertEqual(last_user, "请帮我生成作业")
            self.assertEqual(captured["skill_id"], "physics-homework-generator")
            self.assertEqual(captured["teacher_id"], "teacher-1")
            self.assertIn("teacher-context", str(captured["extra_system"] or ""))
            self.assertIn(
                (
                    "workflow.resolved",
                    {
                        "requested_skill_id": "",
                        "effective_skill_id": "physics-homework-generator",
                        "reason": "auto_rule",
                        "confidence": 0.64,
                        "candidates": [{"skill_id": "physics-homework-generator", "score": 12}],
                    },
                ),
                events,
            )


    def test_compute_chat_reply_respects_teacher_workflow_preflight_before_run_agent(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            calls = {"run_agent": 0}

            deps = ComputeChatReplyDeps(
                detect_role=lambda _text: "teacher",
                diag_log=lambda *_args, **_kwargs: None,
                teacher_assignment_preflight=lambda _req: None,
                resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher-1"),
                teacher_build_context=lambda *_args, **_kwargs: "teacher-context",
                detect_student_study_trigger=lambda _text: False,
                load_profile_file=lambda _path: {},
                data_dir=root / "data",
                build_verified_student_context=lambda _sid, _profile: "",
                build_assignment_detail_cached=lambda *_args, **_kwargs: {},
                find_assignment_for_date=lambda *_args, **_kwargs: None,
                parse_date_str=lambda raw: str(raw or ""),
                build_assignment_context=lambda *_args, **_kwargs: "",
                chat_extra_system_max_chars=6000,
                trim_messages=lambda msgs, role_hint=None: msgs,
                student_inflight=_student_inflight,
                run_agent=lambda *_args, **_kwargs: calls.update({"run_agent": calls["run_agent"] + 1}) or {"reply": "OK"},
                normalize_math_delimiters=lambda text: text,
                resolve_effective_skill=lambda _role, _skill_id, _last_user_text: {
                    "effective_skill_id": "physics-teacher-ops",
                    "reason": "auto_rule",
                },
                teacher_workflow_preflight=lambda _req, effective_skill_id, last_user_text, attachment_context: (
                    "请先提供考试编号或上传成绩单。" if effective_skill_id == "physics-teacher-ops" else None
                ),
            )

            reply, role_hint, _last_user = compute_chat_reply_sync(
                _TeacherReq("请做一次考试分析"),
                deps=deps,
            )

            self.assertEqual(role_hint, "teacher")
            self.assertIn("考试编号", reply)
            self.assertEqual(calls["run_agent"], 0)

    def test_compute_chat_reply_merges_teacher_workflow_extra_system(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured = {"extra_system": None}

            def _run_agent(messages, role_hint, *, extra_system=None, skill_id=None, teacher_id=None, event_sink=None):
                del messages, role_hint, skill_id, teacher_id, event_sink
                captured["extra_system"] = extra_system
                return {"reply": "OK"}

            deps = ComputeChatReplyDeps(
                detect_role=lambda _text: "teacher",
                diag_log=lambda *_args, **_kwargs: None,
                teacher_assignment_preflight=lambda _req: None,
                resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher-1"),
                teacher_build_context=lambda *_args, **_kwargs: "teacher-context",
                detect_student_study_trigger=lambda _text: False,
                load_profile_file=lambda _path: {},
                data_dir=root / "data",
                build_verified_student_context=lambda _sid, _profile: "",
                build_assignment_detail_cached=lambda *_args, **_kwargs: {},
                find_assignment_for_date=lambda *_args, **_kwargs: None,
                parse_date_str=lambda raw: str(raw or ""),
                build_assignment_context=lambda *_args, **_kwargs: "",
                chat_extra_system_max_chars=6000,
                trim_messages=lambda msgs, role_hint=None: msgs,
                student_inflight=_student_inflight,
                run_agent=_run_agent,
                normalize_math_delimiters=lambda text: text,
                resolve_effective_skill=lambda _role, _skill_id, _last_user_text: {
                    "effective_skill_id": "physics-homework-generator",
                    "reason": "auto_rule",
                },
                resolve_teacher_workflow=lambda _req, effective_skill_id, last_user_text, attachment_context: {
                    "workflow_id": effective_skill_id,
                    "workflow_label": "作业生成",
                    "extra_system": "【工作流步骤】先确认作业约束，再生成内容。",
                },
            )

            reply, role_hint, _last_user = compute_chat_reply_sync(
                _TeacherReq("请帮我生成作业"),
                deps=deps,
            )

            self.assertEqual(reply, "OK")
            self.assertEqual(role_hint, "teacher")
            self.assertIn("teacher-context", str(captured["extra_system"] or ""))
            self.assertIn("工作流步骤", str(captured["extra_system"] or ""))


if __name__ == "__main__":
    unittest.main()
