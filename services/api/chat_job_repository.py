from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict


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
        return False


def load_chat_job(job_id: str, deps: ChatJobRepositoryDeps) -> Dict[str, Any]:
    job_dir = chat_job_path(job_id, deps)
    job_path = job_dir / "job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"chat job not found: {job_id}")
    return json.loads(job_path.read_text(encoding="utf-8"))


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
    data: Dict[str, Any] = {}
    if job_path.exists() and not overwrite:
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(updates)
    data["updated_at"] = deps.now_iso()
    deps.atomic_write_json(job_path, data)
    return data
