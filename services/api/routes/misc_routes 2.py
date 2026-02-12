from __future__ import annotations

import json
import logging
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

_log = logging.getLogger(__name__)
_DISK_MIN_BYTES = 100 * 1024 * 1024  # 100 MB


def _check_redis(core) -> dict:
    try:
        redis_client = getattr(core, "REDIS_CLIENT", None)
        if redis_client is None:
            return {"status": "skipped", "reason": "no_client"}
        redis_client.ping()
        return {"status": "ok"}
    except Exception as exc:
        _log.warning("health: Redis ping failed", exc_info=True)
        return {"status": "error", "detail": str(exc)}


def _check_disk(core) -> dict:
    try:
        from pathlib import Path
        data_dir = Path(str(getattr(core, "DATA_DIR", None) or "."))
        # Walk up to an existing ancestor so statvfs doesn't fail on missing dirs
        check_path = data_dir
        while not check_path.exists() and check_path.parent != check_path:
            check_path = check_path.parent
        usage = shutil.disk_usage(str(check_path))
        free_mb = int(usage.free / (1024 * 1024))
        return {"status": "ok" if usage.free >= _DISK_MIN_BYTES else "degraded", "free_mb": free_mb}
    except Exception as exc:
        _log.warning("health: disk check failed", exc_info=True)
        return {"status": "error", "detail": str(exc)}


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        redis_check = _check_redis(core)
        disk_check = _check_disk(core)
        checks = {"redis": redis_check, "disk": disk_check}
        degraded = any(c.get("status") not in ("ok", "skipped") for c in checks.values())
        from fastapi.responses import JSONResponse as _JR
        payload = {"status": "degraded" if degraded else "ok", "checks": checks}
        return _JR(content=payload, status_code=503 if degraded else 200)

    @router.post("/upload")
    async def upload(files: list[UploadFile] = File(...)):
        return await core._upload_files_api_impl(files, deps=core._student_ops_api_deps())

    @router.get("/lessons")
    def lessons():
        return core.list_lessons()

    @router.get("/skills")
    def skills():
        return core.list_skills()

    _INLINE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}

    @router.get("/charts/{run_id}/{file_name}")
    def chart_image_file(run_id: str, file_name: str):
        path = core.resolve_chart_image_path(core.UPLOADS_DIR, run_id, file_name)
        if not path:
            raise HTTPException(status_code=404, detail="chart file not found")
        ext = path.suffix.lower()
        if ext in _INLINE_EXTS:
            return FileResponse(path)
        return FileResponse(path, filename=path.name)

    @router.get("/chart-runs/{run_id}/meta")
    def chart_run_meta(run_id: str):
        path = core.resolve_chart_run_meta_path(core.UPLOADS_DIR, run_id)
        if not path:
            raise HTTPException(status_code=404, detail="chart run not found")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raise HTTPException(status_code=500, detail="failed to read chart run meta")

    return router
