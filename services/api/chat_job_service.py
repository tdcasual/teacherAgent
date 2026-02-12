from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .chat_job_repository import (
    ChatJobRepositoryDeps,
    chat_job_path as _chat_job_path_impl,
    load_chat_job as _load_chat_job_impl,
    write_chat_job as _write_chat_job_impl,
)


def chat_job_path(job_id: str, *, deps: ChatJobRepositoryDeps) -> Path:
    return _chat_job_path_impl(job_id, deps)


def load_chat_job(job_id: str, *, deps: ChatJobRepositoryDeps) -> Dict[str, Any]:
    return _load_chat_job_impl(job_id, deps)


def write_chat_job(
    job_id: str,
    updates: Dict[str, Any],
    *,
    deps: ChatJobRepositoryDeps,
    overwrite: bool = False,
) -> Dict[str, Any]:
    return _write_chat_job_impl(job_id, updates, deps, overwrite=overwrite)
