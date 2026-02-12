from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, UploadFile


def register_misc_general_routes(router: APIRouter, core: Any) -> None:
    @router.post("/upload")
    async def upload(files: list[UploadFile] = File(...)) -> Any:
        return await core._upload_files_api_impl(files, deps=core._student_ops_api_deps())

    @router.get("/lessons")
    def lessons() -> Any:
        return core.list_lessons()

    @router.get("/skills")
    def skills() -> Any:
        return core.list_skills()
