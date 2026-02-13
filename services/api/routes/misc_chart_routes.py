from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..auth_service import AuthError, require_principal

_INLINE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}


def _require_chart_read_access() -> None:
    try:
        require_principal(roles=("teacher", "admin", "service"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_misc_chart_routes(router: APIRouter, core: Any) -> None:
    @router.get("/charts/{run_id}/{file_name}")
    def chart_image_file(run_id: str, file_name: str) -> Any:
        _require_chart_read_access()
        path = core.resolve_chart_image_path(core.UPLOADS_DIR, run_id, file_name)
        if not path:
            raise HTTPException(status_code=404, detail="chart file not found")
        ext = path.suffix.lower()
        if ext in _INLINE_EXTS:
            return FileResponse(path)
        return FileResponse(path, filename=path.name)

    @router.get("/chart-runs/{run_id}/meta")
    def chart_run_meta(run_id: str) -> Any:
        _require_chart_read_access()
        path = core.resolve_chart_run_meta_path(core.UPLOADS_DIR, run_id)
        if not path:
            raise HTTPException(status_code=404, detail="chart run not found")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raise HTTPException(status_code=500, detail="failed to read chart run meta")
