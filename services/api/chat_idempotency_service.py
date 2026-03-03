from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatIdempotencyDeps:
    request_map_dir: Path
    safe_fs_id: Callable[[str, str], str]
    chat_job_exists: Callable[[str], bool]


def request_map_path(request_id: str, deps: ChatIdempotencyDeps) -> Path:
    return deps.request_map_dir / f"{deps.safe_fs_id(request_id, prefix='req')}.txt"  # type: ignore[call-arg]


def request_map_get(request_id: str, deps: ChatIdempotencyDeps) -> Optional[str]:
    request_id = str(request_id or "").strip()
    if not request_id:
        return None
    path = request_map_path(request_id, deps)
    if not path.exists():
        return None
    try:
        job_id = (path.read_text(encoding="utf-8", errors="ignore") or "").strip()
    except Exception:
        _log.warning("failed to read request map for %s", request_id, exc_info=True)
        return None
    if not job_id:
        return None
    try:
        if not deps.chat_job_exists(job_id):
            path.unlink(missing_ok=True)
            return None
    except Exception:
        _log.debug("expired request map cleanup failed for %s", request_id, exc_info=True)
    return job_id


def request_map_set_if_absent(request_id: str, job_id: str, deps: ChatIdempotencyDeps) -> bool:
    request_id = str(request_id or "").strip()
    job_id = str(job_id or "").strip()
    if not request_id or not job_id:
        return False
    path = request_map_path(request_id, deps)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except Exception:
        _log.warning("idempotent lock creation failed for request %s", request_id, exc_info=True)
        return False
    try:
        os.write(fd, job_id.encode("utf-8", errors="ignore"))
        os.fsync(fd)
    finally:
        try:
            os.close(fd)
        except Exception:
            _log.debug("operation failed", exc_info=True)
            pass
    return True


def upsert_chat_request_index(request_id: str, job_id: str, deps: ChatIdempotencyDeps) -> None:
    request_map_set_if_absent(request_id, job_id, deps)


def get_chat_job_id_by_request(request_id: str, deps: ChatIdempotencyDeps) -> Optional[str]:
    return request_map_get(request_id, deps)
