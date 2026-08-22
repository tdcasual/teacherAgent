import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


def load_mcp(tmp_dir: Path, api_key: str = "secret"):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["MCP_API_KEY"] = api_key
    os.environ["MCP_SCRIPT_TIMEOUT_SEC"] = "5"
    import services.mcp.app as mcp_mod

    importlib.reload(mcp_mod)
    (tmp_dir / "data").mkdir(parents=True, exist_ok=True)
    (tmp_dir / "uploads").mkdir(parents=True, exist_ok=True)
    return mcp_mod


def _rpc(client: TestClient, name: str, arguments: dict, api_key: str = "secret"):
    return client.post(
        "/mcp",
        headers={"X-API-Key": api_key},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def test_run_script_rejects_path_outside_allowlist():
    with TemporaryDirectory() as td:
        mcp_mod = load_mcp(Path(td))
        with pytest.raises(HTTPException) as exc:
            mcp_mod.run_script(["python3", "/tmp/evil.py"])
        assert exc.value.status_code == 400
        with pytest.raises(HTTPException):
            mcp_mod.run_script(["python3", str(mcp_mod.APP_ROOT / "scripts" / "grade_submission.py")])
        with pytest.raises(HTTPException):
            mcp_mod.run_script(
                ["python3", str(mcp_mod.APP_ROOT / "skills" / "physics-lesson-capture" / "SKILL.md")]
            )


def test_run_script_allows_skill_and_render_scripts(monkeypatch):
    with TemporaryDirectory() as td:
        mcp_mod = load_mcp(Path(td))
        captured: dict[str, object] = {}

        class _Proc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
            captured.setdefault("cmds", []).append(list(args))
            return _Proc()

        monkeypatch.setattr(mcp_mod.subprocess, "run", _fake_run)
        skill = mcp_mod.APP_ROOT / "skills" / "physics-lesson-capture" / "scripts" / "lesson_capture.py"
        render = mcp_mod.APP_ROOT / "scripts" / "render_assignment_pdf.py"
        assert mcp_mod.run_script(["python3", str(skill)]) == "ok"
        assert mcp_mod.run_script(["python3", str(render)]) == "ok"
        cmds = captured.get("cmds") or []
        assert any(Path(cmd[1]).name == "lesson_capture.py" for cmd in cmds)
        assert any(Path(cmd[1]).name == "render_assignment_pdf.py" for cmd in cmds)


def test_lesson_capture_rejects_source_outside_data_dir():
    with TemporaryDirectory() as td:
        mcp_mod = load_mcp(Path(td))
        client = TestClient(mcp_mod.app)
        res = _rpc(
            client,
            "lesson.capture",
            {"lesson_id": "L1", "topic": "momentum", "sources": ["/etc/passwd"]},
        )
        assert res.status_code == 200
        payload = res.json()
        assert "error" in payload
        assert "DATA_DIR" in payload["error"]["message"] or "UPLOADS_DIR" in payload["error"]["message"]


def test_tool_out_flag_rejects_etc_passwd_and_symlink_escape():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        mcp_mod = load_mcp(tmp)
        client = TestClient(mcp_mod.app)

        passwd = _rpc(client, "assignment.render", {"assignment_id": "A1", "out": "/etc/passwd"})
        assert passwd.status_code == 200
        assert "error" in passwd.json()

        stem = _rpc(
            client,
            "core_example.register",
            {
                "example_id": "CE001",
                "kp_id": "KP-M01",
                "core_model": "model",
                "stem_file": "/etc/passwd",
            },
        )
        assert stem.status_code == 200
        assert "error" in stem.json()

        data_dir = Path(os.environ["DATA_DIR"])
        link = data_dir / "escape_link"
        link.symlink_to("/etc/passwd")
        escaped = _rpc(client, "assignment.render", {"assignment_id": "A1", "out": str(link)})
        assert escaped.status_code == 200
        assert "error" in escaped.json()

        source_escape = _rpc(
            client,
            "lesson.capture",
            {"lesson_id": "L1", "topic": "momentum", "sources": [str(link)]},
        )
        assert source_escape.status_code == 200
        assert "error" in source_escape.json()


def test_contained_paths_under_data_or_uploads_are_accepted(monkeypatch):
    with TemporaryDirectory() as td:
        tmp = Path(td)
        mcp_mod = load_mcp(tmp)
        data_dir = Path(os.environ["DATA_DIR"])
        uploads_dir = Path(os.environ["UPLOADS_DIR"])
        source = data_dir / "lesson.png"
        source.write_text("x", encoding="utf-8")
        out = uploads_dir / "out.pdf"
        captured: dict[str, object] = {}

        class _Proc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
            captured["args"] = list(args)
            return _Proc()

        monkeypatch.setattr(mcp_mod.subprocess, "run", _fake_run)
        client = TestClient(mcp_mod.app)
        res = _rpc(
            client,
            "lesson.capture",
            {"lesson_id": "L1", "topic": "momentum", "sources": [str(source)]},
        )
        assert res.status_code == 200
        assert "result" in res.json()
        assert str(source.resolve()) in (captured.get("args") or [])

        render = _rpc(client, "assignment.render", {"assignment_id": "A1", "out": str(out)})
        assert render.status_code == 200
        assert "result" in render.json()
        assert str(out.resolve()) in (captured.get("args") or [])


def test_core_example_register_lesson_figure_is_basename_not_path(monkeypatch):
    with TemporaryDirectory() as td:
        mcp_mod = load_mcp(Path(td))
        captured: dict[str, object] = {}

        class _Proc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
            captured["args"] = list(args)
            return _Proc()

        monkeypatch.setattr(mcp_mod.subprocess, "run", _fake_run)
        client = TestClient(mcp_mod.app)
        ok = _rpc(
            client,
            "core_example.register",
            {
                "example_id": "CE001",
                "kp_id": "KP-M01",
                "core_model": "model",
                "from_lesson": "L1",
                "lesson_figure": "fig1.png",
            },
        )
        assert ok.status_code == 200
        assert "result" in ok.json()
        args = captured.get("args") or []
        assert "--lesson-figure" in args
        assert "fig1.png" in args
        assert "--from-lesson" in args
        assert "L1" in args

        bad_fig = _rpc(
            client,
            "core_example.register",
            {
                "example_id": "CE001",
                "kp_id": "KP-M01",
                "core_model": "model",
                "lesson_figure": "../etc/passwd",
            },
        )
        assert bad_fig.status_code == 200
        assert "error" in bad_fig.json()

        bad_lesson = _rpc(
            client,
            "core_example.register",
            {
                "example_id": "CE001",
                "kp_id": "KP-M01",
                "core_model": "model",
                "from_lesson": "../../../etc",
            },
        )
        assert bad_lesson.status_code == 200
        assert "error" in bad_lesson.json()
