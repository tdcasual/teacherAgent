"""Profile and student utility functions extracted from app_core.py.

Contains profile loading with caching, role detection, and student helpers.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import PROFILE_CACHE_TTL_SEC

_log = logging.getLogger(__name__)

__all__ = [
    "detect_role",
    "load_profile_file",
    "student_profile_get",
    "student_profile_update",
    "derive_kp_from_profile",
    "apply_derived_profile",
    "safe_assignment_id",
]

_PROFILE_CACHE: Dict[str, Any] = {}
_PROFILE_CACHE_LOCK = threading.Lock()


def reset_profile_cache() -> None:
    """Reset profile cache state. Called by runtime_state on tenant init."""
    global _PROFILE_CACHE, _PROFILE_CACHE_LOCK
    _PROFILE_CACHE = {}
    _PROFILE_CACHE_LOCK = threading.Lock()


def detect_role(text: str) -> Optional[str]:
    normalized = re.sub(r"\s+", "", text or "").lower()
    if "老师" in normalized or "教师" in normalized:
        return "teacher"
    if "学生" in normalized:
        return "student"
    return None


def load_profile_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if PROFILE_CACHE_TTL_SEC > 0:
        key = str(path)
        now = time.monotonic()
        try:
            mtime = path.stat().st_mtime
        except Exception:
            _log.debug("file stat failed", exc_info=True)
            mtime = 0.0
        with _PROFILE_CACHE_LOCK:
            cached = _PROFILE_CACHE.get(key)
            if cached:
                ts, cached_mtime, data = cached
                if (now - ts) <= PROFILE_CACHE_TTL_SEC and cached_mtime == mtime:
                    return data
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if PROFILE_CACHE_TTL_SEC > 0:
            key = str(path)
            now = time.monotonic()
            try:
                mtime = path.stat().st_mtime
            except Exception:
                _log.debug("file stat failed", exc_info=True)
                mtime = 0.0
            with _PROFILE_CACHE_LOCK:
                _PROFILE_CACHE[key] = (now, mtime, data)
        return data
    except Exception:
        _log.warning("failed to load profile at %s", path, exc_info=True)
        return {}

def student_profile_get(student_id: str) -> Dict[str, Any]:
    from .paths import resolve_student_profile_path
    try:
        profile_path = resolve_student_profile_path(student_id)
    except ValueError:
        return {"error": "invalid_student_id", "student_id": student_id}
    if not profile_path.exists():
        return {"error": "profile not found", "student_id": student_id}
    return json.loads(profile_path.read_text(encoding="utf-8"))


def student_profile_update(args: Dict[str, Any]) -> Dict[str, Any]:
    from .config import APP_ROOT
    from .core_utils import run_script
    from .paths import resolve_student_profile_path

    student_id = str(args.get("student_id") or "").strip()
    try:
        resolve_student_profile_path(student_id)
    except ValueError:
        return {"error": "invalid_student_id", "student_id": student_id}
    script = APP_ROOT / "skills" / "student-coach" / "scripts" / "update_profile.py"
    cmd = ["python3", str(script), "--student-id", student_id]
    for key in ("weak_kp", "strong_kp", "medium_kp", "next_focus", "interaction_note",
                "misconceptions", "mastery_json", "completion_status"):
        if args.get(key) is not None:
            cmd += [f"--{key.replace('_', '-')}", str(args.get(key))]
    out = run_script(cmd)
    return {"ok": True, "output": out}


def derive_kp_from_profile(profile: Dict[str, Any]) -> List[str]:
    kp_list = []
    next_focus = profile.get("next_focus")
    if next_focus:
        kp_list.append(str(next_focus))
    for key in ("recent_weak_kp", "recent_medium_kp"):
        for kp in profile.get(key) or []:
            if kp not in kp_list:
                kp_list.append(kp)
    return [kp for kp in kp_list if kp]


def _acquire_profile_lock(lock_path: Path, timeout_sec: float = 8.0) -> bool:
    start = time.monotonic()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(
                    f"pid={os.getpid()} ts={datetime.now().isoformat(timespec='seconds')}\n"
                )
            return True
        except FileExistsError:
            if (time.monotonic() - start) >= timeout_sec:
                return False
            time.sleep(0.05)


def _release_profile_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except OSError:
        _log.debug("failed to release profile lock %s", lock_path, exc_info=True)


def _load_profile_unlocked(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # policy: allowed-broad-except
        _log.warning("failed to load profile at %s", path, exc_info=True)
        return {}
    return payload if isinstance(payload, dict) else {}


def _str_list(value: Any) -> List[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _merge_mastery(profile: Dict[str, Any], incoming: Any) -> None:
    current = profile.get("mastery_by_kp")
    merged: Dict[str, Any] = dict(current) if isinstance(current, dict) else {}
    if isinstance(incoming, dict):
        for key, payload in incoming.items():
            kp = str(key or "").strip()
            if kp and isinstance(payload, dict):
                merged[kp] = payload
    profile["mastery_by_kp"] = merged


def _append_practice_history(profile: Dict[str, Any], derived: Dict[str, Any]) -> None:
    assignment_id = str(derived.get("assignment_id") or "").strip()
    practice_id = str(derived.get("practice_id") or "").strip()
    source = str(derived.get("source") or "").strip()
    question_ids = _str_list(derived.get("question_ids"))
    if not assignment_id and not practice_id and not question_ids and not source:
        return
    history = profile.get("practice_history")
    items = list(history) if isinstance(history, list) else []
    entry: Dict[str, Any] = {
        "assignment_id": assignment_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "question_ids": question_ids,
    }
    if practice_id:
        entry["practice_id"] = practice_id
    items.append(entry)
    profile["practice_history"] = items[-20:]


def apply_derived_profile(
    student_id: str,
    derived: Dict[str, Any],
    *,
    core: Any | None = None,
) -> bool:
    from .paths import resolve_student_profile_path

    payload = derived if isinstance(derived, dict) else {}
    try:
        path = resolve_student_profile_path(student_id, core=core)
    except ValueError:
        _log.warning("apply_derived_profile invalid student_id=%s", student_id)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    if not _acquire_profile_lock(lock_path):
        _log.warning("apply_derived_profile lock timeout path=%s", lock_path)
        return False
    try:
        profile = _load_profile_unlocked(path)
        profile["student_id"] = str(student_id or "").strip()
        profile["last_updated"] = datetime.now().isoformat(timespec="seconds")
        # Empty lists replace; do not skip like update_profile.py.
        profile["recent_weak_kp"] = _str_list(payload.get("recent_weak_kp"))
        profile["recent_medium_kp"] = _str_list(payload.get("recent_medium_kp"))
        profile["recent_strong_kp"] = _str_list(payload.get("recent_strong_kp"))
        profile["next_focus"] = str(payload.get("next_focus") or "")
        _merge_mastery(profile, payload.get("mastery_by_kp"))
        _append_practice_history(profile, payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception:  # policy: allowed-broad-except
        _log.warning("apply_derived_profile failed student_id=%s", student_id, exc_info=True)
        return False
    finally:
        _release_profile_lock(lock_path)


def safe_assignment_id(student_id: str, date_str: str) -> str:
    slug = re.sub(r"[^\w-]+", "_", student_id).strip("_") if student_id else "student"
    return f"AUTO_{slug}_{date_str}"
