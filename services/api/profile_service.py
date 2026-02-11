"""Profile and student utility functions extracted from app_core.py.

Contains profile loading with caching, role detection, and student helpers.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

from .config import PROFILE_CACHE_TTL_SEC

__all__ = [
    "detect_role",
    "load_profile_file",
    "student_profile_get",
    "student_profile_update",
    "derive_kp_from_profile",
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
    from .core_utils import run_script
    from .config import APP_ROOT
    script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
    cmd = ["python3", str(script), "--student-id", args.get("student_id", "")]
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


def safe_assignment_id(student_id: str, date_str: str) -> str:
    slug = re.sub(r"[^\w-]+", "_", student_id).strip("_") if student_id else "student"
    return f"AUTO_{slug}_{date_str}"
