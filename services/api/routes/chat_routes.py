from __future__ import annotations

from fastapi import APIRouter

from ..api_models import ChatRequest, ChatStartRequest


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.post("/chat")
    async def chat(req: ChatRequest):
        return await core.chat_handlers.chat(req, deps=core._chat_handlers_deps())

    @router.post("/chat/start")
    async def chat_start(req: ChatStartRequest):
        return await core.chat_handlers.chat_start(req, deps=core._chat_handlers_deps())

    @router.get("/chat/status")
    async def chat_status(job_id: str):
        return await core.chat_handlers.chat_status(job_id, deps=core._chat_handlers_deps())

    return router
