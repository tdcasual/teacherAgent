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


class TeacherLlmRoutingDelegationTest(unittest.TestCase):
    def test_tool_functions_delegate_to_service_impl(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            sentinel = object()
            calls = {}

            def fake_get(args, *, deps):  # type: ignore[no-untyped-def]
                calls["get"] = {"args": dict(args), "deps": deps}
                return {"ok": True, "fn": "get"}

            def fake_simulate(args, *, deps):  # type: ignore[no-untyped-def]
                calls["simulate"] = {"args": dict(args), "deps": deps}
                return {"ok": True, "fn": "simulate"}

            def fake_propose(args, *, deps):  # type: ignore[no-untyped-def]
                calls["propose"] = {"args": dict(args), "deps": deps}
                return {"ok": True, "fn": "propose"}

            def fake_apply(args, *, deps):  # type: ignore[no-untyped-def]
                calls["apply"] = {"args": dict(args), "deps": deps}
                return {"ok": True, "fn": "apply"}

            def fake_rollback(args, *, deps):  # type: ignore[no-untyped-def]
                calls["rollback"] = {"args": dict(args), "deps": deps}
                return {"ok": True, "fn": "rollback"}

            def fake_proposal_get(args, *, deps):  # type: ignore[no-untyped-def]
                calls["proposal_get"] = {"args": dict(args), "deps": deps}
                return {"ok": True, "fn": "proposal_get"}

            app_mod._teacher_llm_routing_deps = lambda: sentinel  # type: ignore[attr-defined]
            app_mod._teacher_llm_routing_get_impl = fake_get  # type: ignore[attr-defined]
            app_mod._teacher_llm_routing_simulate_impl = fake_simulate  # type: ignore[attr-defined]
            app_mod._teacher_llm_routing_propose_impl = fake_propose  # type: ignore[attr-defined]
            app_mod._teacher_llm_routing_apply_impl = fake_apply  # type: ignore[attr-defined]
            app_mod._teacher_llm_routing_rollback_impl = fake_rollback  # type: ignore[attr-defined]
            app_mod._teacher_llm_routing_proposal_get_impl = fake_proposal_get  # type: ignore[attr-defined]

            self.assertEqual(app_mod.teacher_llm_routing_get({"teacher_id": "t1"}).get("fn"), "get")
            self.assertEqual(app_mod.teacher_llm_routing_simulate({"teacher_id": "t1"}).get("fn"), "simulate")
            self.assertEqual(app_mod.teacher_llm_routing_propose({"teacher_id": "t1", "config": {"enabled": True}}).get("fn"), "propose")
            self.assertEqual(app_mod.teacher_llm_routing_apply({"teacher_id": "t1", "proposal_id": "p1"}).get("fn"), "apply")
            self.assertEqual(app_mod.teacher_llm_routing_rollback({"teacher_id": "t1"}).get("fn"), "rollback")
            self.assertEqual(app_mod.teacher_llm_routing_proposal_get({"teacher_id": "t1", "proposal_id": "p1"}).get("fn"), "proposal_get")

            self.assertIs(calls["get"]["deps"], sentinel)
            self.assertIs(calls["simulate"]["deps"], sentinel)
            self.assertIs(calls["propose"]["deps"], sentinel)
            self.assertIs(calls["apply"]["deps"], sentinel)
            self.assertIs(calls["rollback"]["deps"], sentinel)
            self.assertIs(calls["proposal_get"]["deps"], sentinel)

    def test_ensure_teacher_routing_file_delegates(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            sentinel = object()
            calls = {}
            expected = Path(td) / "route.json"

            def fake_ensure(actor, *, deps):  # type: ignore[no-untyped-def]
                calls["actor"] = actor
                calls["deps"] = deps
                return expected

            app_mod._teacher_llm_routing_deps = lambda: sentinel  # type: ignore[attr-defined]
            app_mod._ensure_teacher_routing_file_impl = fake_ensure  # type: ignore[attr-defined]

            result = app_mod._ensure_teacher_routing_file("teacher_x")
            self.assertEqual(result, expected)
            self.assertEqual(calls.get("actor"), "teacher_x")
            self.assertIs(calls.get("deps"), sentinel)


if __name__ == "__main__":
    unittest.main()
