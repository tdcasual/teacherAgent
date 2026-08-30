from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


def _load_module():
    module_path = Path("scripts/admin_auth_tui.py").resolve()
    spec = importlib.util.spec_from_file_location("admin_auth_tui", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_bool_or_any() -> None:
    mod = _load_module()
    assert mod._parse_bool_or_any("true") is True
    assert mod._parse_bool_or_any("false") is False
    assert mod._parse_bool_or_any("any") is None


def test_parse_selection_expr_by_indices_and_id() -> None:
    mod = _load_module()
    page_items = [
        {"teacher_id": "t1"},
        {"teacher_id": "t2"},
        {"teacher_id": "t3"},
        {"teacher_id": "t4"},
    ]
    picked = mod._parse_selection_expr("1,3-4,id:t2,t99", page_items)
    assert picked == {"t1", "t2", "t3", "t4", "t99"}


def test_apply_filters_and_sort() -> None:
    mod = _load_module()
    state = mod.ViewState(
        filter_query="zhang",
        filter_disabled=False,
        filter_password_set=True,
        sort_field="teacher_name",
        sort_desc=False,
    )
    items = [
        {
            "teacher_id": "b",
            "teacher_name": "张三",
            "email": "a@example.com",
            "is_disabled": False,
            "password_set": True,
            "token_version": 1,
        },
        {
            "teacher_id": "a",
            "teacher_name": "Li",
            "email": "b@example.com",
            "is_disabled": False,
            "password_set": True,
            "token_version": 2,
        },
        {
            "teacher_id": "c",
            "teacher_name": "张老师",
            "email": "zhang@example.com",
            "is_disabled": False,
            "password_set": True,
            "token_version": 3,
        },
    ]
    # Query works on id/name/email; only zhang@example.com should match.
    out = mod._apply_filters(items, state)
    assert [row["teacher_id"] for row in out] == ["c"]


def test_trusted_local_script_entrypoint_works_outside_repo_cwd(tmp_path: Path) -> None:
    script_path = Path("scripts/admin_auth_tui.py").resolve()
    env = os.environ.copy()
    env["DATA_DIR"] = str(tmp_path / "data")
    env["UPLOADS_DIR"] = str(tmp_path / "uploads")
    env["AUTH_REQUIRED"] = "0"

    result = subprocess.run(
        [sys.executable, str(script_path), "--trusted-local"],
        input="q\n",
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        env=env,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "Trusted local mode enabled" in result.stdout


def test_record_history_avoids_deprecated_datetime_utcnow(monkeypatch) -> None:
    mod = _load_module()

    class _FakeNow:
        def isoformat(self, *, timespec: str = "seconds") -> str:
            assert timespec == "seconds"
            return "2026-02-15T16:00:00+00:00"

    class _FakeDateTime:
        @staticmethod
        def now(tz=None):
            assert tz is mod.timezone.utc
            return _FakeNow()

        @staticmethod
        def utcnow():
            raise AssertionError("utcnow should not be called")

    monkeypatch.setattr(mod, "datetime", _FakeDateTime)
    app = mod.AdminAuthTUI(
        base_url="http://127.0.0.1:8000",
        username="",
        password="",
        trusted_local=True,
    )

    app._record_history(action="noop", total=1, success=1, failed=0, detail="ok")
    assert app.state.history[-1]["ts"] == "2026-02-15T16:00:00Z"


def test_identity_commands_use_local_store_in_trusted_mode(capsys) -> None:
    mod = _load_module()
    calls: dict = {}

    class _FakeStore:
        def add_roster(self, **kwargs):
            calls["add_roster"] = kwargs
            return {"ok": True, "warning": "empty_class"}

        def list_subjects(self):
            calls["list_subjects"] = True
            return {"ok": True, "items": [{"subject_id": "physics"}]}

    app = mod.AdminAuthTUI(
        base_url="http://127.0.0.1:8000",
        username="",
        password="",
        trusted_local=True,
    )
    app._local_store = _FakeStore()
    app._cmd_identity("roster", ["add", "t_zhang", "physics", "高二2403班"])
    app._cmd_identity("subject", ["list"])
    assert calls["add_roster"]["teacher_id"] == "t_zhang"
    assert calls["add_roster"]["class_name"] == "高二2403班"
    assert calls["list_subjects"] is True
    out = capsys.readouterr().out
    assert "roster add ok" in out
    assert "warning=empty_class" in out


def test_identity_commands_use_http_when_not_local(monkeypatch, capsys) -> None:
    mod = _load_module()
    seen: dict = {}

    def _fake_request_json(*, method, url, payload=None, bearer_token=None, timeout_sec=15):
        seen["method"] = method
        seen["url"] = url
        seen["payload"] = payload
        seen["token"] = bearer_token
        return 200, {"ok": True, "items": [{"student_id": "S001"}]}

    monkeypatch.setattr(mod, "_request_json", _fake_request_json)
    app = mod.AdminAuthTUI(
        base_url="http://127.0.0.1:8000",
        username="admin",
        password="",
        trusted_local=False,
    )
    app.access_token = "admin-token"
    app._cmd_identity("enrollments", ["list", "physics", "高二2403班"])
    assert seen["method"] == "GET"
    assert seen["url"].startswith("http://127.0.0.1:8000/auth/admin/enrollments?")
    assert "subject_id=physics" in seen["url"]
    assert seen["token"] == "admin-token"
    assert "enrollments list ok" in capsys.readouterr().out
