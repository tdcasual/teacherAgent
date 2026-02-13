from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from services.api.chat_attachment_service import (
    ChatAttachmentDeps,
    ChatAttachmentError,
    MAX_FILE_SIZE_BYTES,
    upload_chat_attachments,
)


class _Upload:
    def __init__(self, name: str, payload: bytes, content_type: str = "text/markdown"):
        self.filename = name
        self.payload = payload
        self.content_type = content_type


def _make_deps(uploads_dir: Path) -> ChatAttachmentDeps:
    counter = {"n": 0}

    async def _save_upload_file(upload: _Upload, dest: Path) -> int:
        data = bytes(getattr(upload, "payload", b""))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return len(data)

    def _uuid_hex() -> str:
        counter["n"] += 1
        return f"{counter['n']:016x}" + ("0" * 16)

    return ChatAttachmentDeps(
        uploads_dir=uploads_dir,
        sanitize_filename=lambda name: Path(str(name or "").strip()).name,
        save_upload_file=_save_upload_file,
        extract_text_from_file=lambda _path, _lang, _mode: "ok",
        xlsx_to_table_preview=lambda _path: "ok",
        xls_to_table_preview=lambda _path: "ok",
        now_iso=lambda: "2026-02-13T00:00:00",
        uuid_hex=_uuid_hex,
    )


def test_upload_chat_attachments_rolls_back_all_dirs_on_late_size_error() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        deps = _make_deps(root / "uploads")
        uploads = [
            _Upload("ok.md", b"ok"),
            _Upload("too_large.md", b"x" * (MAX_FILE_SIZE_BYTES + 1)),
        ]

        with pytest.raises(ChatAttachmentError, match="10MB"):
            asyncio.run(
                upload_chat_attachments(
                    role="teacher",
                    teacher_id="t1",
                    student_id="",
                    session_id="main",
                    request_id="r1",
                    files=uploads,
                    deps=deps,
                )
            )

        attachments_root = root / "uploads" / "chat_attachments"
        if attachments_root.exists():
            assert list(attachments_root.iterdir()) == []
