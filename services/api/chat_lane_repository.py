from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import settings as _settings
from .chat_lane_store_factory import get_chat_lane_store
from .config import (
    CHAT_JOB_CLAIM_TTL_SEC,
    CHAT_LANE_DEBOUNCE_MS,
    REDIS_URL,
    TENANT_ID,
)
from .job_repository import _atomic_write_json
from .paths import resolve_teacher_id, safe_fs_id

# ---------------------------------------------------------------------------
# Module-level mutable state — removed.
# All mutable chat-lane state now lives on the per-tenant app_core module
# and is accessed dynamically via _get_state().
# ---------------------------------------------------------------------------

_log = logging.getLogger(__name__)


def _get_state():
    """Return the current tenant's app_core module (holds all mutable lane state)."""
    from .wiring import get_app_core
    return get_app_core()


# ---------------------------------------------------------------------------
# Lazy import: chat_job_path lives in app_core (thin wrapper around
# chat_job_repository.chat_job_path).  We import it late to avoid a
# circular import at module-load time.
# ---------------------------------------------------------------------------

def _chat_job_path(job_id: str) -> Path:
    from . import app_core as _ac
    return _ac.chat_job_path(job_id)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _chat_last_user_text(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if str(msg.get("role") or "") != "user":
            continue
        return str(msg.get("content") or "")
    return ""


def _chat_text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()


# ---------------------------------------------------------------------------
# Lane ID resolution
# ---------------------------------------------------------------------------

def resolve_chat_lane_id(
    role_hint: Optional[str],
    *,
    session_id: Optional[str] = None,
    student_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> str:
    role = str(role_hint or "unknown").strip().lower() or "unknown"
    sid = safe_fs_id(session_id or "main", prefix="session")
    if role == "student":
        student = safe_fs_id(student_id or "student", prefix="student")
        return f"student:{student}:{sid}"
    if role == "teacher":
        teacher = resolve_teacher_id(teacher_id)
        return f"teacher:{teacher}:{sid}"
    rid = safe_fs_id(request_id or "req", prefix="req")
    return f"unknown:{sid}:{rid}"


def resolve_chat_lane_id_from_job(job: Dict[str, Any]) -> str:
    lane_id = str(job.get("lane_id") or "").strip()
    if lane_id:
        return lane_id
    request_data = job.get("request")
    request: Dict[str, Any] = request_data if isinstance(request_data, dict) else {}
    role = str(job.get("role") or request.get("role") or "unknown")
    session_id = str(job.get("session_id") or "").strip() or None
    student_id = str(job.get("student_id") or request.get("student_id") or "").strip() or None
    teacher_id = str(job.get("teacher_id") or request.get("teacher_id") or "").strip() or None
    request_id = str(job.get("request_id") or "").strip() or None
    return resolve_chat_lane_id(
        role,
        session_id=session_id,
        student_id=student_id,
        teacher_id=teacher_id,
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Lane store singleton
# ---------------------------------------------------------------------------

def _chat_lane_store():
    return get_chat_lane_store(
        tenant_id=str(TENANT_ID or "default").strip() or "default",
        is_pytest=_settings.is_pytest(),
        redis_url=REDIS_URL,
        debounce_ms=CHAT_LANE_DEBOUNCE_MS,
        claim_ttl_sec=CHAT_JOB_CLAIM_TTL_SEC,
    )


def _ensure_lane_state(state: Any) -> Any:
    """Best-effort self-healing for chat lane mutable state on core reload races."""
    if not hasattr(state, "CHAT_JOB_LANES") or not isinstance(getattr(state, "CHAT_JOB_LANES"), dict):
        state.CHAT_JOB_LANES = {}
    if not hasattr(state, "CHAT_JOB_ACTIVE_LANES") or not isinstance(
        getattr(state, "CHAT_JOB_ACTIVE_LANES"), set
    ):
        state.CHAT_JOB_ACTIVE_LANES = set()
    if not hasattr(state, "CHAT_JOB_QUEUED") or not isinstance(getattr(state, "CHAT_JOB_QUEUED"), set):
        state.CHAT_JOB_QUEUED = set()
    if not hasattr(state, "CHAT_JOB_TO_LANE") or not isinstance(getattr(state, "CHAT_JOB_TO_LANE"), dict):
        state.CHAT_JOB_TO_LANE = {}
    cursor = getattr(state, "CHAT_LANE_CURSOR", None)
    if not isinstance(cursor, list) or len(cursor) != 1:
        state.CHAT_LANE_CURSOR = [0]
    if not hasattr(state, "CHAT_LANE_RECENT") or not isinstance(getattr(state, "CHAT_LANE_RECENT"), dict):
        state.CHAT_LANE_RECENT = {}
    return state


# ---------------------------------------------------------------------------
# Lane queue operations (all assume caller holds CHAT_JOB_LOCK)
# ---------------------------------------------------------------------------

def _chat_lane_load_locked(lane_id: str) -> Dict[str, int]:
    _ac = _ensure_lane_state(_get_state())
    if _settings.is_pytest():
        q = _ac.CHAT_JOB_LANES.get(lane_id)
        queued = len(q) if q else 0
        active = 1 if lane_id in _ac.CHAT_JOB_ACTIVE_LANES else 0
        return {"queued": queued, "active": active, "total": queued + active}
    return _chat_lane_store().lane_load(lane_id)


def _chat_find_position_locked(lane_id: str, job_id: str) -> int:
    _ac = _ensure_lane_state(_get_state())
    if _settings.is_pytest():
        q = _ac.CHAT_JOB_LANES.get(lane_id)
        if not q:
            return 0
        for i, jid in enumerate(q, start=1):
            if jid == job_id:
                return i
        return 0
    return _chat_lane_store().find_position(lane_id, job_id)


def _chat_enqueue_locked(job_id: str, lane_id: str) -> int:
    _ac = _ensure_lane_state(_get_state())
    if job_id in _ac.CHAT_JOB_QUEUED or job_id in _ac.CHAT_JOB_TO_LANE:
        return _chat_find_position_locked(lane_id, job_id)
    q = _ac.CHAT_JOB_LANES.setdefault(lane_id, deque())
    q.append(job_id)
    _ac.CHAT_JOB_QUEUED.add(job_id)
    _ac.CHAT_JOB_TO_LANE[job_id] = lane_id
    return len(q)


def _chat_has_pending_locked() -> bool:
    _ac = _ensure_lane_state(_get_state())
    return any(len(q) > 0 for q in _ac.CHAT_JOB_LANES.values())


def _chat_pick_next_locked() -> Tuple[str, str]:
    _ac = _ensure_lane_state(_get_state())
    lanes = [lane for lane, q in _ac.CHAT_JOB_LANES.items() if q]
    if not lanes:
        return "", ""
    total = len(lanes)
    start = _ac.CHAT_LANE_CURSOR[0] % total
    for offset in range(total):
        lane_id = lanes[(start + offset) % total]
        if lane_id in _ac.CHAT_JOB_ACTIVE_LANES:
            continue
        q = _ac.CHAT_JOB_LANES.get(lane_id)
        if not q:
            continue
        job_id = q.popleft()
        _ac.CHAT_JOB_QUEUED.discard(job_id)
        _ac.CHAT_JOB_ACTIVE_LANES.add(lane_id)
        _ac.CHAT_JOB_TO_LANE[job_id] = lane_id
        _ac.CHAT_LANE_CURSOR[0] = (start + offset + 1) % max(1, total)
        return job_id, lane_id
    return "", ""


def _chat_mark_done_locked(job_id: str, lane_id: str) -> None:
    _ac = _ensure_lane_state(_get_state())
    _ac.CHAT_JOB_ACTIVE_LANES.discard(lane_id)
    _ac.CHAT_JOB_TO_LANE.pop(job_id, None)
    q = _ac.CHAT_JOB_LANES.get(lane_id)
    if q is not None and len(q) == 0:
        _ac.CHAT_JOB_LANES.pop(lane_id, None)


# ---------------------------------------------------------------------------
# Recent / dedup helpers
# ---------------------------------------------------------------------------

def _chat_register_recent_locked(lane_id: str, fingerprint: str, job_id: str) -> None:
    _ac = _ensure_lane_state(_get_state())
    if _settings.is_pytest():
        _ac.CHAT_LANE_RECENT[lane_id] = (time.time(), fingerprint, job_id)
        return
    _chat_lane_store().register_recent(lane_id, fingerprint, job_id)


def _chat_recent_job_locked(lane_id: str, fingerprint: str) -> Optional[str]:
    _ac = _ensure_lane_state(_get_state())
    if _settings.is_pytest():
        if CHAT_LANE_DEBOUNCE_MS <= 0:
            return None
        info = _ac.CHAT_LANE_RECENT.get(lane_id)
        if not info:
            return None
        ts, fp, job_id = info
        if fp != fingerprint:
            return None
        if (time.time() - ts) * 1000 > CHAT_LANE_DEBOUNCE_MS:
            return None
        return job_id
    return _chat_lane_store().recent_job(lane_id, fingerprint)


# ---------------------------------------------------------------------------
# Request index / idempotency
# ---------------------------------------------------------------------------

def load_chat_request_index() -> Dict[str, str]:
    _ac = _get_state()
    if _ac.CHAT_IDEMPOTENCY_STATE is None:
        return {}
    request_index_path = _ac.CHAT_IDEMPOTENCY_STATE.request_index_path
    try:
        data = json.loads(request_index_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        _log.warning("load_chat_request_index: corrupt JSON at %s: %s", request_index_path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def _chat_request_map_path(request_id: str) -> Optional[Path]:
    _ac = _get_state()
    if _ac.CHAT_IDEMPOTENCY_STATE is None:
        return None
    return _ac.CHAT_IDEMPOTENCY_STATE.request_map_dir / f"{safe_fs_id(request_id, prefix='req')}.txt"


def _chat_request_map_get(request_id: str) -> Optional[str]:
    request_id = str(request_id or "").strip()
    if not request_id:
        return None
    path = _chat_request_map_path(request_id)
    if path is None:
        return None
    try:
        job_id = (path.read_text(encoding="utf-8", errors="ignore") or "").strip()
    except (FileNotFoundError, OSError):
        return None
    if not job_id:
        return None
    # Best-effort stale cleanup (e.g., crash mid-write).
    try:
        job_path = _chat_job_path(job_id) / "job.json"
        if not job_path.exists():
            path.unlink(missing_ok=True)
            return None
    except Exception:
        _log.debug("_chat_request_map_get: stale cleanup failed for request_id mapping at %s", path)
        pass
    return job_id


def _chat_request_map_set_if_absent(request_id: str, job_id: str) -> bool:
    request_id = str(request_id or "").strip()
    job_id = str(job_id or "").strip()
    if not request_id or not job_id:
        return False
    path = _chat_request_map_path(request_id)
    if path is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except Exception:
        _log.warning("_chat_request_map_set_if_absent: os.open failed for %s", path, exc_info=True)
        return False
    try:
        os.write(fd, job_id.encode("utf-8", errors="ignore"))
        os.fsync(fd)
    finally:
        try:
            os.close(fd)
        except Exception:
            _log.debug("_chat_request_map_set_if_absent: os.close failed for fd=%s", fd)
            pass
    return True


def upsert_chat_request_index(request_id: str, job_id: str) -> None:
    """
    Best-effort idempotency mapping. Primary mapping is per-request lockfile under CHAT_REQUEST_MAP_DIR.
    request_index.json is kept as legacy/debug only.
    """
    _chat_request_map_set_if_absent(request_id, job_id)
    _ac = _get_state()
    if _ac.CHAT_IDEMPOTENCY_STATE is None:
        return
    try:
        with _ac.CHAT_IDEMPOTENCY_STATE.request_index_lock:
            idx = load_chat_request_index()
            idx[str(request_id)] = str(job_id)
            _atomic_write_json(_ac.CHAT_IDEMPOTENCY_STATE.request_index_path, idx)
    except Exception:
        _log.debug("upsert_chat_request_index: legacy index write failed for request_id=%s", request_id, exc_info=True)


def get_chat_job_id_by_request(request_id: str) -> Optional[str]:
    job_id = _chat_request_map_get(request_id)
    if job_id:
        return job_id
    # Fallback to legacy json index (e.g., old jobs created before request map existed).
    _ac = _get_state()
    if _ac.CHAT_IDEMPOTENCY_STATE is None:
        return None
    try:
        with _ac.CHAT_IDEMPOTENCY_STATE.request_index_lock:
            idx = load_chat_request_index()
            legacy = idx.get(str(request_id))
    except Exception:
        _log.warning("get_chat_job_id_by_request: legacy index read failed for request_id=%s", request_id, exc_info=True)
        legacy = None
    if not legacy:
        return None
    try:
        if not (_chat_job_path(legacy) / "job.json").exists():
            return None
    except Exception:
        _log.debug("get_chat_job_id_by_request: stale job path check failed for job_id=%s", legacy)
        return None
    return str(legacy)
