from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..auth_service import AuthError, require_principal

_INLINE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}


def _require_chart_read_access() -> Any:
    try:
        return require_principal(roles=("teacher", "admin", "service"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def _load_chart_meta(path: Any) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # policy: allowed-broad-except
        return {}
    return payload if isinstance(payload, dict) else {}


def _enforce_teacher_chart_owner_access(*, principal: Any, run_id: str, core: Any) -> None:
    if principal is None:
        return
    role = str(getattr(principal, "role", "") or "").strip().lower()
    if role in {"admin", "service"}:
        return
    if role != "teacher":
        raise HTTPException(status_code=403, detail="forbidden_chart_owner")

    meta_path = core.resolve_chart_run_meta_path(core.UPLOADS_DIR, run_id)
    if not meta_path:
        raise HTTPException(status_code=403, detail="forbidden_chart_owner")
    meta = _load_chart_meta(meta_path)
    audit_obj = meta.get("audit")
    audit: dict[str, Any] = audit_obj if isinstance(audit_obj, dict) else {}
    owner_role = str(audit.get("role") or "").strip().lower()
    owner_actor = str(audit.get("actor") or "").strip()
    actor_id = str(getattr(principal, "actor_id", "") or "").strip()
    if owner_role == "teacher" and owner_actor and owner_actor == actor_id:
        return
    raise HTTPException(status_code=403, detail="forbidden_chart_owner")


def register_misc_chart_routes(router: APIRouter, core: Any) -> None:
    @router.get("/charts/{run_id}/{file_name}")
    def chart_image_file(run_id: str, file_name: str) -> Any:
        principal = _require_chart_read_access()
        _enforce_teacher_chart_owner_access(principal=principal, run_id=run_id, core=core)
        path = core.resolve_chart_image_path(core.UPLOADS_DIR, run_id, file_name)
        if not path:
            raise HTTPException(status_code=404, detail="chart file not found")
        ext = path.suffix.lower()
        if ext in _INLINE_EXTS:
            return FileResponse(path)
        return FileResponse(path, filename=path.name)

    @router.get("/chart-runs/{run_id}/meta")
    def chart_run_meta(run_id: str) -> Any:
        principal = _require_chart_read_access()
        _enforce_teacher_chart_owner_access(principal=principal, run_id=run_id, core=core)
        path = core.resolve_chart_run_meta_path(core.UPLOADS_DIR, run_id)
        if not path:
            raise HTTPException(status_code=404, detail="chart run not found")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # policy: allowed-broad-except
            raise HTTPException(status_code=500, detail="failed to read chart run meta")
