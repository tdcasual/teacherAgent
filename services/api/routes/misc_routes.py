from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        return {"status": "ok"}

    @router.post("/upload")
    async def upload(files: list[UploadFile] = File(...)):
        return await core._upload_files_api_impl(files, deps=core._student_ops_api_deps())

    @router.get("/lessons")
    async def lessons():
        return core.list_lessons()

    @router.get("/skills")
    async def skills():
        return core.list_skills()

    @router.get("/charts/{run_id}/{file_name}")
    async def chart_image_file(run_id: str, file_name: str):
        path = core.resolve_chart_image_path(core.UPLOADS_DIR, run_id, file_name)
        if not path:
            raise HTTPException(status_code=404, detail="chart file not found")
        return FileResponse(path)

    @router.get("/chart-runs/{run_id}/meta")
    async def chart_run_meta(run_id: str):
        path = core.resolve_chart_run_meta_path(core.UPLOADS_DIR, run_id)
        if not path:
            raise HTTPException(status_code=404, detail="chart run not found")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raise HTTPException(status_code=500, detail="failed to read chart run meta")

    return router
