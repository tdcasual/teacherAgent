from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from ..api_models import ChatRequest, ChatStartRequest
from ..auth_service import (
    AuthError,
    bind_chat_request_to_principal,
    enforce_chat_job_access,
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
from ..chat_event_stream_service import encode_sse_event, load_chat_events_incremental


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


@dataclass
class _ChatStreamState:
    cursor: int
    log_offset: int | None = None
    signal_version: int = 0
    terminal_idle_loops: int = 0
    keepalive_ticks: int = 0


def _ensure_chat_stream_access(job_id: str, core: Any) -> None:
    try:
        job = core.load_chat_job(job_id)
        enforce_chat_job_access(job)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="job not found")
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def _resolve_stream_cursor(request: Request, last_event_id: int) -> int:
    cursor = max(0, int(last_event_id or 0))
    header_last_event_id = str(request.headers.get("last-event-id") or "").strip()
    if not header_last_event_id:
        return cursor
    try:
        return max(cursor, int(header_last_event_id))
    except Exception:
        return cursor


def _stream_event_chunks(events: list[dict[str, Any]], state: _ChatStreamState) -> list[str]:
    chunks: list[str] = []
    for item in events:
        event_id = int(item.get("event_id") or 0)
        if event_id > state.cursor:
            state.cursor = event_id
        chunks.append(encode_sse_event(item))
    return chunks


def _advance_keepalive(keepalive_ticks: int) -> tuple[int, str]:
    keepalive_ticks += 1
    if keepalive_ticks >= 20:
        return 0, ": keepalive\n\n"
    return keepalive_ticks, ""


def _terminal_idle_state(
    core: Any,
    *,
    job_id: str,
    events: list[dict[str, Any]],
    terminal_idle_loops: int,
) -> tuple[int, bool]:
    try:
        status_job = core.load_chat_job(job_id)
    except FileNotFoundError:
        return terminal_idle_loops, True
    status = str(status_job.get("status") or "").strip().lower()
    if status in {"done", "failed", "cancelled"} and not events:
        terminal_idle_loops += 1
    else:
        terminal_idle_loops = 0
    return terminal_idle_loops, terminal_idle_loops >= 3


async def _wait_for_stream_signal(
    deps: Any,
    *,
    job_id: str,
    signal_version: int,
    idle_wait_sec: float,
) -> int:
    if callable(deps.wait_job_event):
        try:
            return await asyncio.to_thread(
                deps.wait_job_event,
                job_id,
                signal_version,
                idle_wait_sec,
            )
        except Exception:
            await asyncio.sleep(0.25)
            return signal_version
    await asyncio.sleep(0.25)
    return signal_version


async def _iter_chat_stream_events(
    request: Request,
    *,
    job_id: str,
    initial_cursor: int,
    deps: Any,
    core: Any,
) -> Any:
    state = _ChatStreamState(cursor=initial_cursor)
    idle_wait_sec = 1.0
    yield "retry: 1000\n\n"
    while True:
        if await request.is_disconnected():
            break
        events, state.log_offset = load_chat_events_incremental(
            job_id,
            deps=deps,
            after_event_id=state.cursor,
            offset_hint=state.log_offset,
            limit=300,
        )
        if events:
            for chunk in _stream_event_chunks(events, state):
                yield chunk
            state.terminal_idle_loops = 0
            state.keepalive_ticks = 0
        else:
            state.keepalive_ticks, keepalive = _advance_keepalive(state.keepalive_ticks)
            if keepalive:
                yield keepalive
        state.terminal_idle_loops, should_stop = _terminal_idle_state(
            core,
            job_id=job_id,
            events=events,
            terminal_idle_loops=state.terminal_idle_loops,
        )
        if should_stop:
            break
        if events:
            continue
        state.signal_version = await _wait_for_stream_signal(
            deps,
            job_id=job_id,
            signal_version=state.signal_version,
            idle_wait_sec=idle_wait_sec,
        )


def _chat_stream_response(
    request: Request,
    *,
    job_id: str,
    last_event_id: int,
    core: Any,
) -> StreamingResponse:
    _ensure_chat_stream_access(job_id, core)
    deps = core.chat_event_stream_deps()
    cursor = _resolve_stream_cursor(request, last_event_id)
    return StreamingResponse(
        _iter_chat_stream_events(
            request,
            job_id=job_id,
            initial_cursor=cursor,
            deps=deps,
            core=core,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _register_chat_core_routes(router: APIRouter, core: Any) -> None:
    @router.post("/chat")
    async def chat(req: ChatRequest) -> Any:
        bound = _bind_or_raise(req)
        return await core.chat(bound)

    @router.post("/chat/start")
    async def chat_start(req: ChatStartRequest) -> Any:
        bound = _bind_or_raise(req)
        return await core.chat_start(bound)

    @router.get("/chat/status")
    async def chat_status(job_id: str) -> Any:
        return await core.chat_status(job_id)


def _register_chat_stream_route(router: APIRouter, core: Any) -> None:
    @router.get("/chat/stream")
    async def chat_stream(
        request: Request,
        job_id: str,
        last_event_id: int = Query(default=0),
    ) -> Any:
        return _chat_stream_response(
            request,
            job_id=job_id,
            last_event_id=last_event_id,
            core=core,
        )


def register_chat_routes(router: APIRouter, core: Any) -> None:
    _register_chat_core_routes(router, core)
    _register_chat_stream_route(router, core)


def register_chat_attachment_routes(router: APIRouter, core: Any) -> None:
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
