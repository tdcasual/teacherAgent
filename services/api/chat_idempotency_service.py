from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class ChatIdempotencyDeps:
    request_map_dir: Path
    request_index_path: Path
    request_index_lock: Any
    safe_fs_id: Callable[[str, str], str]
    chat_job_exists: Callable[[str], bool]
    atomic_write_json: Callable[[Path, Any], None]


def load_chat_request_index(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: Dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out


def request_map_path(request_id: str, deps: ChatIdempotencyDeps) -> Path:
    return deps.request_map_dir / f"{deps.safe_fs_id(request_id, prefix='req')}.txt"


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
        return None
    if not job_id:
        return None
    try:
        if not deps.chat_job_exists(job_id):
            path.unlink(missing_ok=True)
            return None
    except Exception:
        pass
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
        return False
    try:
        os.write(fd, job_id.encode("utf-8", errors="ignore"))
    finally:
        try:
            os.close(fd)
        except Exception:
            pass
    return True


def upsert_chat_request_index(request_id: str, job_id: str, deps: ChatIdempotencyDeps) -> None:
    request_map_set_if_absent(request_id, job_id, deps)
    try:
        with deps.request_index_lock:
            idx = load_chat_request_index(deps.request_index_path)
            idx[str(request_id)] = str(job_id)
            deps.atomic_write_json(deps.request_index_path, idx)
    except Exception:
        pass


def get_chat_job_id_by_request(request_id: str, deps: ChatIdempotencyDeps) -> Optional[str]:
    job_id = request_map_get(request_id, deps)
    if job_id:
        return job_id
    try:
        with deps.request_index_lock:
            idx = load_chat_request_index(deps.request_index_path)
            legacy = idx.get(str(request_id))
    except Exception:
        legacy = None
    if not legacy:
        return None
    try:
        if not deps.chat_job_exists(legacy):
            return None
    except Exception:
        return None
    return legacy
