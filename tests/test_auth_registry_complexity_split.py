from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import services.api.auth_registry_service as auth_registry_service


def _issues(path: str) -> list[dict]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            path,
            "--select",
            "C901",
            "--config",
            "lint.mccabe.max-complexity=10",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "").strip()
    return json.loads(output) if output else []


def test_auth_registry_hotspots_removed() -> None:
    target = "services/api/auth_registry_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def export_tokens(" in source
    assert "def _list_teacher_identities(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_export_tokens_keeps_teacher_identity_merge_behavior(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    store = auth_registry_service.AuthRegistryStore(
        db_path=data_dir / "auth" / "auth_registry.sqlite3",
        data_dir=data_dir,
    )
    monkeypatch.setattr(auth_registry_service, "resolve_teacher_id", lambda value: str(value or "").strip())
    monkeypatch.setattr(auth_registry_service, "default_teacher_id", lambda: "fallback_teacher")

    merge_dir = data_dir / "teacher_workspaces" / "teacher_merge"
    merge_dir.mkdir(parents=True, exist_ok=True)
    (merge_dir / "USER.md").write_text(
        "# Teacher Profile\n- name: 合并老师\n- email: merge@example.com\n",
        encoding="utf-8",
    )
    new_dir = data_dir / "teacher_workspaces" / "teacher_new"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "USER.md").write_text(
        "# Teacher Profile\n- name: 新老师\n- email: new@example.com\n",
        encoding="utf-8",
    )

    store._ensure_teacher_auth(
        teacher_id="teacher_merge",
        teacher_name="(unknown)",
        email=None,
        regenerate_token=False,
    )

    payload = store.export_tokens(
        role="teacher",
        ids=["teacher_merge", "teacher_new", "fallback_teacher"],
        actor_id="admin_a",
        actor_role="admin",
    )

    assert payload["ok"] is True
    assert payload["count"] == 3
    assert "teacher_id,teacher_name,email,token" in str(payload["csv"] or "")

    items = {str(item["teacher_id"]): item for item in payload["items"]}
    assert items["teacher_merge"]["teacher_name"] == "合并老师"
    assert items["teacher_merge"]["email"] == "merge@example.com"
    assert items["teacher_new"]["teacher_name"] == "新老师"
    assert items["teacher_new"]["email"] == "new@example.com"
    assert items["fallback_teacher"]["teacher_name"] == "fallback_teacher"
    assert items["fallback_teacher"]["email"] == ""
