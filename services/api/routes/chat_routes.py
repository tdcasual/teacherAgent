from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from ..api_models import ChatRequest, ChatStartRequest
from ..auth_service import (
    AuthError,
    bind_chat_request_to_principal,
    resolve_student_scope,
    resolve_teacher_scope,
)
from ..chat_attachment_service import (
    ChatAttachmentDeps,
    ChatAttachmentError,
    delete_chat_attachment,
    get_chat_attachment_status,
    upload_chat_attachments,
)


def _bind_or_raise(req: ChatRequest | ChatStartRequest) -> ChatRequest | ChatStartRequest:
    try:
        return bind_chat_request_to_principal(req)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def _chat_attachment_deps(core: Any) -> ChatAttachmentDeps:
    return ChatAttachmentDeps(
        uploads_dir=core.UPLOADS_DIR,
        sanitize_filename=core.sanitize_filename,
        save_upload_file=core.save_upload_file,
        extract_text_from_file=core.extract_text_from_file,
        xlsx_to_table_preview=core.xlsx_to_table_preview,
        xls_to_table_preview=core.xls_to_table_preview,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        uuid_hex=lambda: uuid.uuid4().hex,
    )


def _bind_attachment_scope(
    *,
    role: str,
    teacher_id: str,
    student_id: str,
) -> tuple[str, str, str]:
    role_norm = str(role or "").strip().lower()
    if role_norm == "teacher":
        try:
            teacher_scope = resolve_teacher_scope(teacher_id, required_for_admin=False) or ""
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return "teacher", str(teacher_scope or "").strip(), ""
    if role_norm == "student":
        try:
            student_scope = resolve_student_scope(student_id, required_for_admin=False) or ""
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return "student", "", str(student_scope or "").strip()
    raise HTTPException(status_code=400, detail="role must be teacher or student")


def build_router(core: Any) -> APIRouter:
    router = APIRouter()

    @router.post("/chat")
    async def chat(req: ChatRequest) -> Any:
        bound = _bind_or_raise(req)
        return await core.chat_handlers.chat(bound, deps=core._chat_handlers_deps())

    @router.post("/chat/start")
    async def chat_start(req: ChatStartRequest) -> Any:
        bound = _bind_or_raise(req)
        return await core.chat_handlers.chat_start(bound, deps=core._chat_handlers_deps())

    @router.get("/chat/status")
    async def chat_status(job_id: str) -> Any:
        return await core.chat_handlers.chat_status(job_id, deps=core._chat_handlers_deps())

    @router.post("/chat/attachments")
    async def chat_attachment_upload(
        role: str = Form(...),
        session_id: str = Form(""),
        request_id: str = Form(""),
        teacher_id: str = Form(""),
        student_id: str = Form(""),
        files: list[UploadFile] = File(...),
        language: str = Form("zh"),
        ocr_mode: str = Form("FREE_OCR"),
    ) -> Any:
        role_norm, teacher_scope, student_scope = _bind_attachment_scope(
            role=role,
            teacher_id=teacher_id,
            student_id=student_id,
        )
        if role_norm == "teacher":
            teacher_scope = core.resolve_teacher_id(teacher_scope)
        try:
            return await upload_chat_attachments(
                role=role_norm,
                teacher_id=teacher_scope,
                student_id=student_scope,
                session_id=session_id,
                request_id=request_id,
                files=files,
                language=language,
                ocr_mode=ocr_mode,
                deps=_chat_attachment_deps(core),
            )
        except ChatAttachmentError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/chat/attachments/status")
    async def chat_attachment_status(
        role: str,
        session_id: str,
        attachment_ids: list[str] = Query(default=[]),
        teacher_id: str = "",
        student_id: str = "",
    ) -> Any:
        role_norm, teacher_scope, student_scope = _bind_attachment_scope(
            role=role,
            teacher_id=teacher_id,
            student_id=student_id,
        )
        if role_norm == "teacher":
            teacher_scope = core.resolve_teacher_id(teacher_scope)
        try:
            return get_chat_attachment_status(
                role=role_norm,
                teacher_id=teacher_scope,
                student_id=student_scope,
                session_id=session_id,
                attachment_ids=attachment_ids,
                deps=_chat_attachment_deps(core),
            )
        except ChatAttachmentError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.delete("/chat/attachments/{attachment_id}")
    async def chat_attachment_delete(
        attachment_id: str,
        role: str,
        session_id: str,
        teacher_id: str = "",
        student_id: str = "",
    ) -> Any:
        role_norm, teacher_scope, student_scope = _bind_attachment_scope(
            role=role,
            teacher_id=teacher_id,
            student_id=student_id,
        )
        if role_norm == "teacher":
            teacher_scope = core.resolve_teacher_id(teacher_scope)
        try:
            return delete_chat_attachment(
                role=role_norm,
                teacher_id=teacher_scope,
                student_id=student_scope,
                session_id=session_id,
                attachment_id=attachment_id,
                deps=_chat_attachment_deps(core),
            )
        except ChatAttachmentError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return router
