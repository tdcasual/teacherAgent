from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

_log = logging.getLogger(__name__)



@dataclass(frozen=True)
class AssignmentUploadJobDeps:
    upload_job_dir: Path
    now_iso: Callable[[], str]
    atomic_write_json: Callable[[Path, Dict[str, Any]], None]
    queue: Any
    lock: Any
    event: Any
    process_upload_job: Callable[[str], None]
    diag_log: Callable[[str, Dict[str, Any]], None]
    sleep: Callable[[float], None]


def _safe_job_component(job_id: str) -> str:
    raw = str(job_id or "")
    safe = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if safe:
        return safe
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"job_{digest}"


def upload_job_path(job_id: str, deps: AssignmentUploadJobDeps) -> Path:
    return deps.upload_job_dir / _safe_job_component(job_id)


def load_upload_job(job_id: str, deps: AssignmentUploadJobDeps) -> Dict[str, Any]:
    job_dir = upload_job_path(job_id, deps)
    job_path = job_dir / "job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"job not found: {job_id}")
    return json.loads(job_path.read_text(encoding="utf-8"))


def write_upload_job(
    job_id: str,
    updates: Dict[str, Any],
    deps: AssignmentUploadJobDeps,
    overwrite: bool = False,
) -> Dict[str, Any]:
    job_dir = upload_job_path(job_id, deps)
    job_dir.mkdir(parents=True, exist_ok=True)
    job_path = job_dir / "job.json"
    data: Dict[str, Any] = {}
    if job_path.exists() and not overwrite:
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            _log.debug("JSON parse failed", exc_info=True)
            data = {}
    data.update(updates)
    data["updated_at"] = deps.now_iso()
    deps.atomic_write_json(job_path, data)
    return data


def enqueue_upload_job(job_id: str, deps: AssignmentUploadJobDeps) -> None:
    with deps.lock:
        if job_id not in deps.queue:
            deps.queue.append(job_id)
    deps.event.set()


def scan_pending_upload_jobs(deps: AssignmentUploadJobDeps) -> None:
    deps.upload_job_dir.mkdir(parents=True, exist_ok=True)
    for job_path in deps.upload_job_dir.glob("*/job.json"):
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            _log.debug("directory creation failed", exc_info=True)
            continue
        status = str(data.get("status") or "")
        job_id = str(data.get("job_id") or "")
        if status in {"queued", "processing"} and job_id:
            enqueue_upload_job(job_id, deps)


def upload_job_worker_step(deps: AssignmentUploadJobDeps) -> bool:
    job_id = ""
    with deps.lock:
        if deps.queue:
            job_id = deps.queue.popleft()
        if not deps.queue:
            deps.event.clear()
    if not job_id:
        deps.sleep(0.1)
        return False
    try:
        deps.process_upload_job(job_id)
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        deps.diag_log("upload.job.failed", {"job_id": job_id, "error": str(exc)[:200]})
        write_upload_job(
            job_id,
            {
                "status": "failed",
                "error": str(exc)[:200],
            },
            deps=deps,
        )
    return True


def upload_job_worker_loop(deps: AssignmentUploadJobDeps) -> None:
    while True:
        deps.event.wait()
        upload_job_worker_step(deps)


def start_upload_worker(
    deps: AssignmentUploadJobDeps,
    *,
    is_worker_started: Callable[[], bool],
    set_worker_started: Callable[[bool], None],
    thread_factory: Callable[..., Any],
) -> None:
    if is_worker_started():
        return
    scan_pending_upload_jobs(deps)
    thread = thread_factory(target=lambda: upload_job_worker_loop(deps), daemon=True)
    thread.start()
    set_worker_started(True)
