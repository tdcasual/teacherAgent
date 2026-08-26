from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from services.api import tool_confirm_service as mod
from services.common.tool_registry import DEFAULT_TOOL_REGISTRY, ToolDef


def test_mutating_flags_match_allowlist() -> None:
    for name in DEFAULT_TOOL_REGISTRY.names():
        tool = DEFAULT_TOOL_REGISTRY.require(name)
        assert bool(tool.mutating) == (name in mod.MUTATING_TOOL_NAMES)
        mcp = tool.to_mcp()
        openai = tool.to_openai()
        assert "mutating" not in mcp
        assert "mutating" not in openai
        assert "mutating" not in json.dumps(mcp)
        assert "mutating" not in json.dumps(openai)


def test_create_pending_is_0600_ttl_hmac_and_single_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "unit-secret")
    args = {"student_id": "S1", "weak_kp": "力学"}
    created = mod.create_tool_confirm_pending(
        tool="student.profile.update",
        args=args,
        actor_id="teacher-1",
        job_id="job-1",
        lane_id="lane-1",
        tool_call_id="call-1",
        data_dir=tmp_path,
        now=1_700_000_000,
    )
    confirm_id = str(created["confirm_id"])
    path = tmp_path / "tool_confirms" / f"{confirm_id}.json"
    assert path.is_file()
    assert (path.stat().st_mode & 0o777) == 0o600
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["tool"] == "student.profile.update"
    assert payload["args"] == args
    assert payload["exp"] == 1_700_000_000 + 300
    expected = mod.make_confirm_id(
        tool="student.profile.update",
        args=args,
        actor_id="teacher-1",
        job_id="job-1",
        exp=payload["exp"],
    )
    assert confirm_id == expected
    first = mod.consume_tool_confirm_pending(confirm_id, actor_id="teacher-1", data_dir=tmp_path, now=1_700_000_010)
    assert first.get("ok") is True
    second = mod.consume_tool_confirm_pending(confirm_id, actor_id="teacher-1", data_dir=tmp_path, now=1_700_000_010)
    assert second.get("error") == "confirm_not_found"


def test_consume_rejects_wrong_actor_expired_and_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "unit-secret")
    created = mod.create_tool_confirm_pending(
        tool="assignment.generate",
        args={"assignment_id": "A1"},
        actor_id="teacher-1",
        job_id="job-9",
        data_dir=tmp_path,
        now=1_700_000_000,
    )
    confirm_id = str(created["confirm_id"])
    forbidden = mod.consume_tool_confirm_pending(confirm_id, actor_id="other", data_dir=tmp_path, now=1_700_000_010)
    assert forbidden.get("error") == "forbidden"
    expired = mod.consume_tool_confirm_pending(confirm_id, actor_id="teacher-1", data_dir=tmp_path, now=1_700_000_400)
    assert expired.get("error") == "confirm_not_found"
    missing = mod.consume_tool_confirm_pending("ab" * 32, actor_id="teacher-1", data_dir=tmp_path)
    assert missing.get("error") == "confirm_not_found"


def test_maybe_confirmation_required_skips_when_confirmed_or_readonly() -> None:
    tool = ToolDef(name="exam.get", description="x", parameters={"type": "object"}, mutating=False)
    assert mod.maybe_confirmation_required(tool=tool, name="exam.get", args={}, confirmed=False) is None
    mutating = DEFAULT_TOOL_REGISTRY.require("student.profile.update")
    assert mod.maybe_confirmation_required(tool=mutating, name="student.profile.update", args={"student_id": "s"}, confirmed=True) is None


def test_confirm_teacher_tool_executes_once_and_resumes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "unit-secret")
    created = mod.create_tool_confirm_pending(
        tool="student.profile.update",
        args={"student_id": "S1"},
        actor_id="teacher-1",
        job_id="job-1",
        lane_id="lane-1",
        data_dir=tmp_path,
        now=int(time.time()),
    )
    calls: list[dict] = []
    writes: list[tuple[str, dict]] = []
    resumes: list[tuple[str, str]] = []

    class _Core:
        TENANT_ID = "tenant-a"

        def tool_dispatch(self, name, args, role, **kwargs):
            calls.append({"name": name, "args": args, "confirmed": kwargs.get("confirmed")})
            return {"ok": True, "tool": name}

        def write_chat_job(self, job_id, updates):
            writes.append((job_id, dict(updates)))

    monkeypatch.setattr(mod, "_resume_after_confirm", lambda job_id, lane_id, *, tenant_id=None: resumes.append((job_id, lane_id)) or {"ok": True})
    result = mod.confirm_teacher_tool(
        confirm_id=str(created["confirm_id"]),
        confirmed=True,
        actor_id="teacher-1",
        core=_Core(),
        data_dir=tmp_path,
    )
    assert result.get("ok") is True
    assert calls == [{"name": "student.profile.update", "args": {"student_id": "S1"}, "confirmed": True}]
    assert writes[0][0] == "job-1"
    assert writes[0][1]["confirm_resume_result"]["ok"] is True
    assert resumes == [("job-1", "lane-1")]
    again = mod.confirm_teacher_tool(
        confirm_id=str(created["confirm_id"]),
        confirmed=True,
        actor_id="teacher-1",
        core=_Core(),
        data_dir=tmp_path,
    )
    assert again.get("error") == "confirm_not_found"
    assert len(calls) == 1
