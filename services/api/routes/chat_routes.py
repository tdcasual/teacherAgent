from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException

from ..api_models import ChatRequest, ChatStartRequest
from ..auth_service import AuthError, bind_chat_request_to_principal


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.post("/chat")
    async def chat(req: ChatRequest):
        try:
            req = bind_chat_request_to_principal(req)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return await core.chat_handlers.chat(req, deps=core._chat_handlers_deps())

    @router.post("/chat/start")
    async def chat_start(req: ChatStartRequest):
        try:
            req = bind_chat_request_to_principal(req)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return await core.chat_handlers.chat_start(req, deps=core._chat_handlers_deps())

    @router.get("/chat/status")
    async def chat_status(job_id: str):
        return await core.chat_handlers.chat_status(job_id, deps=core._chat_handlers_deps())

    return router
