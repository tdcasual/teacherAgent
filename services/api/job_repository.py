from __future__ import annotations

import fcntl
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from .chat_lock_service import (
    ChatLockDeps,
    release_lockfile as _release_lockfile_impl,
    try_acquire_lockfile as _try_acquire_lockfile_impl,
)
from .paths import exam_job_path, upload_job_path
from .upload_io_service import sanitize_filename_io
from .upload_text_service import save_upload_file as _save_upload_file_impl

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Atomic JSON write
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use unique temp names so concurrent writers don't contend on one *.tmp file.
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        try:
            os.write(fd, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            _log.debug("failed to clean up temp file %s", tmp)
            pass


# ---------------------------------------------------------------------------
# Upload job I/O
# ---------------------------------------------------------------------------

def load_upload_job(job_id: str) -> Dict[str, Any]:
    job_dir = upload_job_path(job_id)
    job_path = job_dir / "job.json"
    try:
        data = json.loads(job_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"job not found: {job_id}")
    if not isinstance(data, dict):
        raise ValueError(f"job data for {job_id} is not a JSON object")
    return data

def write_upload_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    job_dir = upload_job_path(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_path = job_dir / "job.json"
    lock_path = job_dir / ".job.lock"
    lock_fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        data: Dict[str, Any] = {}
        if job_path.exists() and not overwrite:
            try:
                data = json.loads(job_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                _log.warning("corrupt job.json for %s, resetting: %s", job_id, exc)
                data = {}
        if not isinstance(data, dict):
            data = {}
        data.update(updates)
        data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _atomic_write_json(job_path, data)
        return data
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


# ---------------------------------------------------------------------------
# Exam job I/O
# ---------------------------------------------------------------------------

def load_exam_job(job_id: str) -> Dict[str, Any]:
    job_dir = exam_job_path(job_id)
    job_path = job_dir / "job.json"
    try:
        data = json.loads(job_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"exam job not found: {job_id}")
    if not isinstance(data, dict):
        raise ValueError(f"exam job data for {job_id} is not a JSON object")
    return data

def write_exam_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    job_dir = exam_job_path(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_path = job_dir / "job.json"
    lock_path = job_dir / ".job.lock"
    lock_fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        data: Dict[str, Any] = {}
        if job_path.exists() and not overwrite:
            try:
                data = json.loads(job_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                _log.warning("corrupt exam job.json for %s, resetting: %s", job_id, exc)
                data = {}
        if not isinstance(data, dict):
            data = {}
        data.update(updates)
        data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _atomic_write_json(job_path, data)
        return data
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


# ---------------------------------------------------------------------------
# Cross-process lockfile (shared implementation)
# ---------------------------------------------------------------------------

def _is_pid_alive(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        _log.debug("unexpected error checking pid %s liveness", pid)
        return True
    return True


def _try_acquire_lockfile(path: Path, ttl_sec: int) -> bool:
    return _try_acquire_lockfile_impl(
        path,
        ttl_sec,
        ChatLockDeps(
            now_ts=time.time,
            now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
            get_pid=os.getpid,
            is_pid_alive=_is_pid_alive,
        ),
    )


def _release_lockfile(path: Path) -> None:
    _release_lockfile_impl(path)


# ---------------------------------------------------------------------------
# File upload helpers
# ---------------------------------------------------------------------------

async def save_upload_file(upload: UploadFile, dest: Path, chunk_size: int = 1024 * 1024) -> int:
    return await _save_upload_file_impl(
        upload,
        dest,
        chunk_size=chunk_size,
        run_in_threadpool=run_in_threadpool,
    )

def sanitize_filename(name: str) -> str:
    return sanitize_filename_io(name)
