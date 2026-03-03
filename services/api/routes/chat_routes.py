from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .chat_route_handlers import register_chat_attachment_routes, register_chat_routes


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    register_chat_routes(router, core)
    register_chat_attachment_routes(router, core)
    return router
