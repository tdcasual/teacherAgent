import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class ToolDispatchSecurityTest(unittest.TestCase):
    def test_lesson_capture_rejects_outside_paths(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            res = app_mod.get_core().tool_dispatch(
                "lesson.capture",
                {"lesson_id": "L1", "topic": "T", "sources": ["/etc/passwd"]},
                role="teacher",
                confirmed=True,
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "source_not_found_or_outside_app_root")

    def test_core_example_render_rejects_outside_out_path(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            res = app_mod.get_core().tool_dispatch(
                "core_example.render",
                {"example_id": "CE001", "out": "/etc/out.pdf"},
                role="teacher",
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "out_outside_app_root")

    def test_core_example_register_rejects_outside_files(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            res = app_mod.get_core().tool_dispatch(
                "core_example.register",
                {"example_id": "CE001", "kp_id": "KP-M01", "core_model": "M", "stem_file": "/etc/passwd"},
                role="teacher",
                confirmed=True,
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "stem_file_not_found_or_outside_app_root")

    def test_removed_teacher_llm_routing_tool_is_unknown(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            result = app_mod.get_core().tool_dispatch("teacher.llm_routing.get", {}, role="teacher")
            self.assertIn("error", result)
            self.assertEqual(result["error"], "unknown tool: teacher.llm_routing.get")

    def test_chart_exec_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.get_core().tool_dispatch("chart.exec", {"python_code": "print('hi')"}, role="student")
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

    def test_chart_agent_run_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.get_core().tool_dispatch("chart.agent.run", {"task": "plot"}, role="student")
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

    def test_chart_agent_run_rejects_opencode_engine_for_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            result = app_mod.get_core().tool_dispatch("chart.agent.run", {"task": "plot", "engine": "opencode"}, role="teacher", confirmed=True)
            self.assertIn("error", result)
            self.assertEqual(result["error"], "opencode_forbidden")
            self.assertEqual(result.get("status_code"), 400)

    def test_assignment_generate_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.get_core().tool_dispatch(
                "assignment.generate",
                {"assignment_id": "HW1", "subject_id": "physics"},
                role="student",
            )
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

    def test_assignment_generate_forbids_other_teacher_existing_assignment(self):
        from services.api.tool_dispatch_service import ToolDispatchDeps, tool_dispatch

        class _Registry:
            def get(self, name):
                return name if name == "assignment.generate" else None

            def validate_arguments(self, _name, _args):
                return []

        generated = {}

        def _deps():
            return ToolDispatchDeps(
                tool_registry=_Registry(),
                list_assignments=lambda owner_teacher_id=None: {},
                list_lessons=lambda: {},
                lesson_capture=lambda args: {},
                student_search=lambda query, limit, allowed=None: {},
                student_profile_get=lambda student_id: {},
                student_profile_update=lambda args: {},
                student_import=lambda args: {},
                assignment_generate=lambda args: generated.__setitem__("ok", True) or {"ok": True},
                assignment_render=lambda args: {},
                save_assignment_requirements=lambda *a, **k: {},
                parse_date_str=lambda raw: str(raw or ""),
                core_example_search=lambda args: {},
                core_example_register=lambda args: {},
                core_example_render=lambda args: {},
                chart_agent_run=lambda args: {},
                chart_exec=lambda args: {},
                resolve_teacher_id=lambda raw: str(raw or ""),
                ensure_teacher_workspace=lambda teacher_id: Path("/tmp") / str(teacher_id),
                teacher_workspace_dir=lambda teacher_id: Path("/tmp") / str(teacher_id),
                teacher_workspace_file=lambda teacher_id, name: Path("/tmp") / str(teacher_id) / name,
                teacher_daily_memory_path=lambda teacher_id, date_str=None: Path("/tmp") / str(teacher_id) / "d.md",
                teacher_read_text=lambda path, max_chars=8000: "",
                teacher_memory_search=lambda teacher_id, query, limit=5: {},
                teacher_memory_propose=lambda *a, **k: {},
                teacher_memory_apply=lambda *a, **k: {},
                assignment_owner_id=lambda assignment_id: "t_owner" if assignment_id == "HW_A" else None,
            )

        stolen = tool_dispatch(
            "assignment.generate",
            {"assignment_id": "HW_A", "subject_id": "physics"},
            role="teacher",
            teacher_id="t_thief",
            deps=_deps(),
            confirmed=True,
        )
        self.assertEqual(stolen.get("error"), "forbidden_assignment_owner")
        self.assertNotIn("ok", generated)

        created = tool_dispatch(
            "assignment.generate",
            {"assignment_id": "HW_NEW", "subject_id": "physics"},
            role="teacher",
            teacher_id="t_thief",
            deps=_deps(),
            confirmed=True,
        )
        self.assertTrue(created.get("ok"))


class _BindRegistry:
    def __init__(self, names):
        self._names = set(names)

    def get(self, name):
        return name if name in self._names else None

    def validate_arguments(self, _name, _args):
        return []


def _bind_deps(*, enrolled=None, captured=None, extra=None):
    from services.api.tool_dispatch_service import ToolDispatchDeps

    captured = captured if captured is not None else {}
    enrolled_ids = set(enrolled or [])

    def _search(query, limit, allowed=None):
        captured["search"] = (query, limit, allowed)
        if allowed is not None and not allowed:
            return {"matches": []}
        return {"matches": [{"student_id": sid} for sid in (allowed or [])]}

    def _profile_get(student_id):
        captured["profile_get"] = student_id
        return {"ok": True, "student_id": student_id}

    def _profile_update(args):
        captured["profile_update"] = dict(args)
        return {"ok": True, "args": args}

    names = {
        "teacher.memory.get",
        "teacher.workspace.init",
        "teacher.memory.search",
        "teacher.memory.propose",
        "teacher.memory.apply",
        "student.search",
        "student.profile.get",
        "student.profile.update",
        "student.import",
        "assignment.render",
        "assignment.generate",
    }
    kwargs = dict(
        tool_registry=_BindRegistry(names),
        list_assignments=lambda owner_teacher_id=None: {},
        list_lessons=lambda: {},
        lesson_capture=lambda args: {},
        student_search=_search,
        student_profile_get=_profile_get,
        student_profile_update=_profile_update,
        student_import=lambda args: captured.__setitem__("import", True) or {"ok": True},
        assignment_generate=lambda args: {},
        assignment_render=lambda args: captured.__setitem__("render", dict(args)) or {"ok": True, "pdf": "x"},
        save_assignment_requirements=lambda *a, **k: {},
        parse_date_str=lambda raw: str(raw or ""),
        core_example_search=lambda args: {},
        core_example_register=lambda args: {},
        core_example_render=lambda args: {},
        chart_agent_run=lambda args: {},
        chart_exec=lambda args: {},
        resolve_teacher_id=lambda raw: str(raw or ""),
        ensure_teacher_workspace=lambda teacher_id: Path("/tmp") / str(teacher_id),
        teacher_workspace_dir=lambda teacher_id: Path("/tmp") / str(teacher_id),
        teacher_workspace_file=lambda teacher_id, name: Path("/tmp") / str(teacher_id) / name,
        teacher_daily_memory_path=lambda teacher_id, date_str=None: Path("/tmp") / str(teacher_id) / "d.md",
        teacher_read_text=lambda path, max_chars=8000: "mem",
        teacher_memory_search=lambda teacher_id, query, limit=5: {},
        teacher_memory_propose=lambda *a, **k: {"ok": True},
        teacher_memory_apply=lambda *a, **k: {"ok": True},
        list_enrolled_student_ids=lambda _tid: set(enrolled_ids),
        assignment_owner_id=lambda assignment_id: "t_me" if assignment_id == "HW1" else None,
    )
    if extra:
        kwargs.update(extra)
    return ToolDispatchDeps(**kwargs), captured


class ToolBindAuthzTest(unittest.TestCase):
    def test_teacher_memory_get_ignores_foreign_teacher_id(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, _captured = _bind_deps()
        stolen = tool_dispatch(
            "teacher.memory.get",
            {"teacher_id": "t_other"},
            role="teacher",
            teacher_id="t_me",
            deps=deps,
        )
        self.assertEqual(stolen.get("error"), "forbidden_teacher_scope")
        self.assertEqual(stolen.get("status_code"), 403)

        own = tool_dispatch(
            "teacher.memory.get",
            {"teacher_id": "t_me"},
            role="teacher",
            teacher_id="t_me",
            deps=deps,
        )
        self.assertTrue(own.get("ok"))
        self.assertEqual(own.get("teacher_id"), "t_me")

        missing = tool_dispatch(
            "teacher.memory.get",
            {},
            role="teacher",
            deps=deps,
        )
        self.assertEqual(missing.get("error"), "teacher_id_required")
        self.assertEqual(missing.get("status_code"), 400)

    def test_workspace_init_ignores_foreign_teacher_id(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, _captured = _bind_deps()
        stolen = tool_dispatch(
            "teacher.workspace.init",
            {"teacher_id": "t_other"},
            role="teacher",
            teacher_id="t_me",
            deps=deps,
            confirmed=True,
        )
        self.assertEqual(stolen.get("error"), "forbidden_teacher_scope")
        self.assertEqual(stolen.get("status_code"), 403)

    def test_args_get_teacher_id_or_bound_is_absent_in_source(self):
        root = Path(__file__).resolve().parents[1]
        needle = 'args.get("teacher_id") or teacher_id'
        hits = []
        for folder in (root / "services", root / "skills"):
            if not folder.exists():
                continue
            for path in folder.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if needle in text:
                    hits.append(str(path.relative_to(root)))
        self.assertEqual(hits, [])

    def test_teacher_memory_get_denied_for_admin(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, _captured = _bind_deps()
        denied = tool_dispatch(
            "teacher.memory.get",
            {"teacher_id": "t_me"},
            role="admin",
            teacher_id="admin",
            deps=deps,
        )
        self.assertEqual(denied.get("error"), "permission denied")

        empty_role = tool_dispatch(
            "teacher.memory.get",
            {"teacher_id": "t_me"},
            role="",
            teacher_id="t_me",
            deps=deps,
        )
        self.assertEqual(empty_role.get("error"), "permission denied")

    def test_student_profile_update_rejects_dotdot_student_id(self):
        from services.api.profile_service import student_profile_update
        from services.api.tool_dispatch_service import tool_dispatch

        deps, captured = _bind_deps(enrolled={"S1"})
        denied = tool_dispatch(
            "student.profile.update",
            {"student_id": "../etc/passwd"},
            role="teacher",
            teacher_id="t_me",
            deps=deps,
            confirmed=True,
        )
        self.assertEqual(denied.get("error"), "forbidden_student_scope")
        self.assertNotIn("profile_update", captured)

        jail = student_profile_update({"student_id": "../etc/passwd"})
        self.assertEqual(jail.get("error"), "invalid_student_id")

    def test_teacher_student_profile_get_forbidden_out_of_roster(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, captured = _bind_deps(enrolled={"S1"})
        denied = tool_dispatch(
            "student.profile.get",
            {"student_id": "S2"},
            role="teacher",
            teacher_id="t_me",
            deps=deps,
        )
        self.assertEqual(denied.get("error"), "forbidden_student_scope")
        self.assertEqual(denied.get("status_code"), 403)
        self.assertNotIn("profile_get", captured)

        allowed = tool_dispatch(
            "student.profile.get",
            {"student_id": "S1"},
            role="teacher",
            teacher_id="t_me",
            deps=deps,
        )
        self.assertEqual(allowed.get("student_id"), "S1")

        missing = tool_dispatch(
            "student.profile.get",
            {"student_id": "S1"},
            role="teacher",
            deps=deps,
        )
        self.assertEqual(missing.get("error"), "teacher_id_required")

    def test_teacher_student_search_omits_out_of_roster(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, captured = _bind_deps(enrolled={"S1"})
        out = tool_dispatch(
            "student.search",
            {"query": "S", "limit": 5},
            role="teacher",
            teacher_id="t_me",
            deps=deps,
        )
        self.assertEqual(captured.get("search")[2], {"S1"})
        self.assertEqual(out.get("matches"), [{"student_id": "S1"}])

        empty_deps, _c = _bind_deps(enrolled=set())
        empty = tool_dispatch(
            "student.search",
            {"query": "S", "limit": 5},
            role="teacher",
            teacher_id="t_me",
            deps=empty_deps,
        )
        self.assertEqual(empty.get("matches"), [])

        missing = tool_dispatch(
            "student.search",
            {"query": "S"},
            role="teacher",
            deps=deps,
        )
        self.assertEqual(missing.get("error"), "teacher_id_required")

        student_denied = tool_dispatch(
            "student.search",
            {"query": "S"},
            role="student",
            actor_id="S1",
            deps=deps,
        )
        self.assertEqual(student_denied.get("error"), "permission denied")

    def test_student_profile_get_self_ok(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, captured = _bind_deps()
        out = tool_dispatch(
            "student.profile.get",
            {},
            role="student",
            actor_id="S1",
            deps=deps,
        )
        self.assertEqual(out.get("student_id"), "S1")
        self.assertEqual(captured.get("profile_get"), "S1")

        same = tool_dispatch(
            "student.profile.get",
            {"student_id": "S1"},
            role="student",
            actor_id="S1",
            deps=deps,
        )
        self.assertEqual(same.get("student_id"), "S1")

    def test_student_profile_get_foreign_forbidden(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, captured = _bind_deps()
        denied = tool_dispatch(
            "student.profile.get",
            {"student_id": "S2"},
            role="student",
            actor_id="S1",
            deps=deps,
        )
        self.assertEqual(denied.get("error"), "forbidden_student_scope")
        self.assertEqual(denied.get("status_code"), 403)
        self.assertNotIn("profile_get", captured)

    def test_student_profile_get_missing_bound_400(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, captured = _bind_deps()
        missing = tool_dispatch(
            "student.profile.get",
            {"student_id": "S1"},
            role="student",
            deps=deps,
        )
        self.assertEqual(missing.get("error"), "student_id_required")
        self.assertEqual(missing.get("status_code"), 400)
        self.assertNotIn("profile_get", captured)

    def test_student_import_tool_returns_410(self):
        from services.api.tool_dispatch_service import tool_dispatch

        deps, captured = _bind_deps()
        out = tool_dispatch(
            "student.import",
            {},
            role="teacher",
            teacher_id="t_me",
            deps=deps,
            confirmed=True,
        )
        self.assertEqual(out.get("error"), "gone")
        self.assertEqual(out.get("status_code"), 410)
        self.assertNotIn("import", captured)


class AssignmentRenderJailTest(unittest.TestCase):
    def _render_deps(self, tmp: Path):
        from services.api.assignment_generate_tool_service import AssignmentGenerateToolDeps

        captured = {"cmd": None}

        return (
            AssignmentGenerateToolDeps(
                app_root=tmp,
                optional_assignment_date=lambda value: None,
                ensure_requirements_for_assignment=lambda *_a: None,
                run_script=lambda cmd: captured.__setitem__("cmd", list(cmd)) or "ok",
                postprocess_assignment_meta=lambda *_a, **_k: None,
                diag_log=lambda *_a, **_k: None,
            ),
            captured,
        )

    def test_assignment_render_explicit_out_rejects_app_root_outside_data_dir(self):
        from services.api import config as config_mod
        from services.api.assignment_generate_tool_service import assignment_render

        with TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            data_dir.mkdir()
            old_data = os.environ.get("DATA_DIR")
            old_uploads = os.environ.get("UPLOADS_DIR")
            os.environ["DATA_DIR"] = str(data_dir)
            os.environ["UPLOADS_DIR"] = str(root / "uploads")
            config_mod.reset_default_config()
            try:
                deps, captured = self._render_deps(root)
                outside = assignment_render(
                    {"assignment_id": "HW1", "out": str(root / "output" / "pdf" / "hw.pdf")},
                    deps=deps,
                )
                self.assertEqual(outside.get("error"), "out_outside_data_dir")
                self.assertIsNone(captured["cmd"])

                abs_etc = assignment_render(
                    {"assignment_id": "HW1", "out": "/etc/hw.pdf"},
                    deps=deps,
                )
                self.assertEqual(abs_etc.get("error"), "out_outside_data_dir")

                inside = data_dir / "out" / "hw.pdf"
                ok = assignment_render(
                    {"assignment_id": "HW1", "out": str(inside)},
                    deps=deps,
                )
                self.assertTrue(ok.get("ok"))
                self.assertEqual(ok.get("pdf"), str(inside.resolve()))
                self.assertIn("--out", captured["cmd"])
                self.assertIn("--data-dir", captured["cmd"])
                self.assertIn("--app-root", captured["cmd"])
            finally:
                if old_data is None:
                    os.environ.pop("DATA_DIR", None)
                else:
                    os.environ["DATA_DIR"] = old_data
                if old_uploads is None:
                    os.environ.pop("UPLOADS_DIR", None)
                else:
                    os.environ["UPLOADS_DIR"] = old_uploads
                config_mod.reset_default_config()

    def test_assignment_render_default_path_unchanged(self):
        from services.api import config as config_mod
        from services.api.assignment_generate_tool_service import assignment_render

        with TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            data_dir.mkdir()
            old_data = os.environ.get("DATA_DIR")
            os.environ["DATA_DIR"] = str(data_dir)
            config_mod.reset_default_config()
            try:
                deps, captured = self._render_deps(root)
                out = assignment_render({"assignment_id": "HW1"}, deps=deps)
                self.assertTrue(out.get("ok"))
                self.assertEqual(out.get("pdf"), "output/pdf/assignment_HW1.pdf")
                self.assertNotIn("--out", captured["cmd"] or [])
                self.assertIn("--data-dir", captured["cmd"])
                self.assertIn("--app-root", captured["cmd"])
            finally:
                if old_data is None:
                    os.environ.pop("DATA_DIR", None)
                else:
                    os.environ["DATA_DIR"] = old_data
                config_mod.reset_default_config()


if __name__ == "__main__":
    unittest.main()

