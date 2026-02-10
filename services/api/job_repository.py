from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from .paths import exam_job_path, upload_job_path
from .upload_io_service import sanitize_filename_io
from .upload_text_service import save_upload_file as _save_upload_file_impl


# ---------------------------------------------------------------------------
# Atomic JSON write
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use unique temp names so concurrent writers don't contend on one *.tmp file.
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Upload job I/O
# ---------------------------------------------------------------------------

def load_upload_job(job_id: str) -> Dict[str, Any]:
    job_dir = upload_job_path(job_id)
    job_path = job_dir / "job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"job not found: {job_id}")
    return json.loads(job_path.read_text(encoding="utf-8"))

def write_upload_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    job_dir = upload_job_path(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_path = job_dir / "job.json"
    data: Dict[str, Any] = {}
    if job_path.exists() and not overwrite:
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(updates)
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write_json(job_path, data)
    return data


# ---------------------------------------------------------------------------
# Exam job I/O
# ---------------------------------------------------------------------------

def load_exam_job(job_id: str) -> Dict[str, Any]:
    job_dir = exam_job_path(job_id)
    job_path = job_dir / "job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"exam job not found: {job_id}")
    return json.loads(job_path.read_text(encoding="utf-8"))

def write_exam_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    job_dir = exam_job_path(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_path = job_dir / "job.json"
    data: Dict[str, Any] = {}
    if job_path.exists() and not overwrite:
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(updates)
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write_json(job_path, data)
    return data


# ---------------------------------------------------------------------------
# Cross-process lockfile
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
        return True
    return True


def _read_lock_pid(path: Path) -> int:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        payload = json.loads(raw)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        return int(payload.get("pid") or 0)
    except Exception:
        return 0


def _try_acquire_lockfile(path: Path, ttl_sec: int) -> bool:
    """
    Cross-process lock using O_EXCL lockfile. Used to prevent duplicate job processing
    under uvicorn multi-worker mode.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for _attempt in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                pid = _read_lock_pid(path)
                if pid > 0 and not _is_pid_alive(pid):
                    path.unlink(missing_ok=True)
                    continue
            except Exception:
                pass
            try:
                age = now - float(path.stat().st_mtime)
                if ttl_sec > 0 and age > float(ttl_sec):
                    path.unlink(missing_ok=True)
                    continue
            except Exception:
                pass
            return False
        except Exception:
            return False
        try:
            payload = {"pid": os.getpid(), "ts": datetime.now().isoformat(timespec="seconds")}
            os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8", errors="ignore"))
        finally:
            try:
                os.close(fd)
            except Exception:
                pass
        return True
    return False


def _release_lockfile(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


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
