import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


def load_mcp(tmp_dir: Path, api_key: str = "secret", bound_teacher_id: str = ""):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["MCP_API_KEY"] = api_key
    os.environ["MCP_SCRIPT_TIMEOUT_SEC"] = "5"
    if bound_teacher_id:
        os.environ["MCP_BOUND_TEACHER_ID"] = bound_teacher_id
    else:
        os.environ.pop("MCP_BOUND_TEACHER_ID", None)
    import services.mcp.app as mcp_mod

    importlib.reload(mcp_mod)
    (tmp_dir / "data").mkdir(parents=True, exist_ok=True)
    (tmp_dir / "uploads").mkdir(parents=True, exist_ok=True)
    return mcp_mod


def _seed_assignment(data_dir: Path, assignment_id: str, teacher_id: str) -> None:
    folder = data_dir / "assignments" / assignment_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "meta.json").write_text(
        json.dumps({"assignment_id": assignment_id, "teacher_id": teacher_id}, ensure_ascii=False),
        encoding="utf-8",
    )


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
        lesson = mcp_mod.APP_ROOT / "skills" / "physics-lesson-capture" / "scripts" / "lesson_capture.py"
        core = mcp_mod.APP_ROOT / "skills" / "physics-core-examples" / "scripts" / "register_core_example.py"
        coach = mcp_mod.APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
        render = mcp_mod.APP_ROOT / "scripts" / "render_assignment_pdf.py"

        with pytest.raises(HTTPException) as lesson_exc:
            mcp_mod.run_script(["python3", str(lesson)])
        assert lesson_exc.value.status_code == 400
        with pytest.raises(HTTPException) as core_exc:
            mcp_mod.run_script(["python3", str(core)])
        assert core_exc.value.status_code == 400

        assert mcp_mod.run_script(["python3", str(coach)]) == "ok"
        assert mcp_mod.run_script(["python3", str(render)]) == "ok"
        cmds = captured.get("cmds") or []
        assert any(Path(cmd[1]).name == "update_profile.py" for cmd in cmds)
        assert any(Path(cmd[1]).name == "render_assignment_pdf.py" for cmd in cmds)


def test_tool_out_flag_rejects_etc_passwd_and_symlink_escape():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        mcp_mod = load_mcp(tmp, bound_teacher_id="t_bound")
        data_dir = Path(os.environ["DATA_DIR"])
        _seed_assignment(data_dir, "A1", "t_bound")
        client = TestClient(mcp_mod.app)

        passwd = _rpc(client, "assignment.render", {"assignment_id": "A1", "out": "/etc/passwd"})
        assert passwd.status_code == 200
        assert "error" in passwd.json()

        link = data_dir / "escape_link"
        link.symlink_to("/etc/passwd")
        escaped = _rpc(client, "assignment.render", {"assignment_id": "A1", "out": str(link)})
        assert escaped.status_code == 200
        assert "error" in escaped.json()


def test_contained_paths_under_data_or_uploads_are_accepted(monkeypatch):
    with TemporaryDirectory() as td:
        tmp = Path(td)
        mcp_mod = load_mcp(tmp, bound_teacher_id="t_bound")
        data_dir = Path(os.environ["DATA_DIR"])
        uploads_dir = Path(os.environ["UPLOADS_DIR"])
        _seed_assignment(data_dir, "A1", "t_bound")
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
        render = _rpc(client, "assignment.render", {"assignment_id": "A1", "out": str(out)})
        assert render.status_code == 200
        assert "result" in render.json()
        assert str(out.resolve()) in (captured.get("args") or [])
