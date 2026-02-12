from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..api_models import ChatRequest, ChatStartRequest
from ..auth_service import AuthError, bind_chat_request_to_principal


def _bind_or_raise(req: ChatRequest | ChatStartRequest) -> ChatRequest | ChatStartRequest:
    try:
        return bind_chat_request_to_principal(req)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.post("/chat")
    async def chat(req: ChatRequest):
        bound = _bind_or_raise(req)
        return await core.chat_handlers.chat(bound, deps=core._chat_handlers_deps())

    @router.post("/chat/start")
    async def chat_start(req: ChatStartRequest):
        bound = _bind_or_raise(req)
        return await core.chat_handlers.chat_start(bound, deps=core._chat_handlers_deps())

    @router.get("/chat/status")
    async def chat_status(job_id: str):
        return await core.chat_handlers.chat_status(job_id, deps=core._chat_handlers_deps())

    return router
