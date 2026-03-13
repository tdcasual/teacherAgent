from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from services.api.chat_attachment_service import (
    ChatAttachmentDeps,
    resolve_chat_attachment_context,
)


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


def _deps(root: Path) -> ChatAttachmentDeps:
    async def _save_upload_file(upload: object, dest: Path) -> int:
        raise AssertionError(f"unexpected save for {upload} -> {dest}")

    return ChatAttachmentDeps(
        uploads_dir=root / "uploads",
        sanitize_filename=lambda name: Path(str(name or "").strip()).name,
        save_upload_file=_save_upload_file,
        extract_text_from_file=lambda _path, _lang, _mode: "ok",
        xlsx_to_table_preview=lambda _path: "ok",
        xls_to_table_preview=lambda _path: "ok",
        now_iso=lambda: "2026-02-13T00:00:00",
        uuid_hex=lambda: "1234567890abcdef1234567890abcdef",
    )


def test_chat_attachment_hotspots_removed() -> None:
    target = "services/api/chat_attachment_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "async def upload_chat_attachments(" in source
    assert "def resolve_chat_attachment_context(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_resolve_chat_attachment_context_truncates_ready_attachment(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    attachment_id = "att_deadbeef"
    attachment_dir = deps.uploads_dir / "chat_attachments" / attachment_id
    attachment_dir.mkdir(parents=True, exist_ok=True)
    (attachment_dir / "meta.json").write_text(
        json.dumps(
            {
                "attachment_id": attachment_id,
                "role": "teacher",
                "teacher_id": "t1",
                "student_id": "",
                "session_id": "main",
                "file_name": "notes.md",
                "status": "ready",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (attachment_dir / "extracted.txt").write_text("abcdefghijklmnopqrstuvwxyz", encoding="utf-8")

    result = resolve_chat_attachment_context(
        role="teacher",
        teacher_id="t1",
        student_id="",
        session_id="main",
        attachment_ids=[attachment_id],
        deps=deps,
        max_chars=18,
    )

    assert result["ready_attachment_ids"] == [attachment_id]
    assert "attachment_context_truncated" in result["warnings"]
    assert result["attachment_context"].endswith("…")
