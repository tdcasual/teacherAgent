from __future__ import annotations

import logging
import shutil
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

_log = logging.getLogger(__name__)
_DISK_MIN_BYTES = 100 * 1024 * 1024  # 100 MB


def _check_redis(core: Any) -> dict:
    try:
        redis_client = getattr(core, "REDIS_CLIENT", None)
        if redis_client is None:
            return {"status": "skipped", "reason": "no_client"}
        redis_client.ping()
        return {"status": "ok"}
    except Exception as exc:
        _log.warning("health: Redis ping failed", exc_info=True)
        return {"status": "error", "detail": str(exc)}


def _check_disk(core: Any) -> dict:
    try:
        from pathlib import Path

        data_dir = Path(str(getattr(core, "DATA_DIR", None) or "."))
        # Walk up to an existing ancestor so statvfs doesn't fail on missing dirs
        check_path = data_dir
        while not check_path.exists() and check_path.parent != check_path:
            check_path = check_path.parent
        usage = shutil.disk_usage(str(check_path))
        free_mb = int(usage.free / (1024 * 1024))
        return {
            "status": "ok" if usage.free >= _DISK_MIN_BYTES else "degraded",
            "free_mb": free_mb,
        }
    except Exception as exc:
        _log.warning("health: disk check failed", exc_info=True)
        return {"status": "error", "detail": str(exc)}


def register_misc_health_routes(router: APIRouter, core: Any) -> None:
    @router.get("/health")
    async def health():
        redis_check = _check_redis(core)
        disk_check = _check_disk(core)
        checks = {"redis": redis_check, "disk": disk_check}
        degraded = any(c.get("status") not in ("ok", "skipped") for c in checks.values())
        payload = {"status": "degraded" if degraded else "ok", "checks": checks}
        return JSONResponse(content=payload, status_code=503 if degraded else 200)
