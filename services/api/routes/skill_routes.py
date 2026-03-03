"""No-op skill router.

Teacher skill CRUD/import endpoints were intentionally removed.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def build_router(core: Any) -> APIRouter:
    return APIRouter()
