from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .chat_job_state_machine import (
    normalize_chat_job_status,
    transition_chat_job_status,
)

_log = logging.getLogger(__name__)



@dataclass(frozen=True)
class ChatJobRepositoryDeps:
    chat_job_dir: Path
    atomic_write_json: Callable[[Path, Any], None]
    now_iso: Callable[[], str]


def _safe_job_component(job_id: str) -> str:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if safe:
        return safe
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"job_{digest}"


def chat_job_path(job_id: str, deps: ChatJobRepositoryDeps) -> Path:
    return deps.chat_job_dir / _safe_job_component(job_id)


def chat_job_exists(job_id: str, deps: ChatJobRepositoryDeps) -> bool:
    try:
        return (chat_job_path(job_id, deps) / "job.json").exists()
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return False


def load_chat_job(job_id: str, deps: ChatJobRepositoryDeps) -> Dict[str, Any]:
    job_dir = chat_job_path(job_id, deps)
    job_path = job_dir / "job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"chat job not found: {job_id}")
    return json.loads(job_path.read_text(encoding="utf-8"))


def _read_existing_job(job_path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(job_path.read_text(encoding="utf-8"))
    except Exception:
        _log.debug("JSON parse failed", exc_info=True)
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_status_update(
    *,
    job_id: str,
    updates: Dict[str, Any],
    existing: Dict[str, Any],
    existed: bool,
    overwrite: bool,
) -> Optional[str]:
    if "status" not in updates:
        return None
    target = updates.get("status")
    # First insert may persist queued without a prior record; missing current → queued.
    is_create = not existed
    if overwrite and is_create and normalize_chat_job_status(target) == "queued":
        return "queued"
    current = existing.get("status") if existed else None
    try:
        return transition_chat_job_status(current, target)
    except ValueError:
        _log.warning(
            "rejected illegal chat job status write job_id=%s transition=%s->%s",
            job_id,
            normalize_chat_job_status(current),
            normalize_chat_job_status(target),
        )
        raise


def write_chat_job(
    job_id: str,
    updates: Dict[str, Any],
    deps: ChatJobRepositoryDeps,
    *,
    overwrite: bool = False,
) -> Dict[str, Any]:
    job_dir = chat_job_path(job_id, deps)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_path = job_dir / "job.json"
    existed = job_path.exists()
    existing: Dict[str, Any] = _read_existing_job(job_path) if existed else {}
    resolved_status = _resolve_status_update(
        job_id=job_id,
        updates=updates,
        existing=existing,
        existed=existed,
        overwrite=overwrite,
    )
    data: Dict[str, Any] = dict(existing) if existed and not overwrite else {}
    data.update(updates)
    if resolved_status is not None:
        data["status"] = resolved_status
    data["updated_at"] = deps.now_iso()
    deps.atomic_write_json(job_path, data)
    return data
