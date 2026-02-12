"""Assignment data loading functions extracted from app_core.py.

Contains assignment meta/requirements loading and detail caching.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, Tuple

from .config import ASSIGNMENT_DETAIL_CACHE_TTL_SEC
from .profile_service import load_profile_file

import logging
_log = logging.getLogger(__name__)

__all__ = [
    "load_assignment_meta",
    "load_assignment_requirements",
    "_assignment_detail_fingerprint",
    "build_assignment_detail_cached",
]

_ASSIGNMENT_DETAIL_CACHE: Dict[Any, Any] = {}
_ASSIGNMENT_DETAIL_CACHE_LOCK = threading.Lock()


def reset_assignment_cache() -> None:
    """Reset assignment detail cache. Called by runtime_state on tenant init."""
    global _ASSIGNMENT_DETAIL_CACHE, _ASSIGNMENT_DETAIL_CACHE_LOCK
    _ASSIGNMENT_DETAIL_CACHE = {}
    _ASSIGNMENT_DETAIL_CACHE_LOCK = threading.Lock()


def load_assignment_meta(folder: Path) -> Dict[str, Any]:
    meta_path = folder / "meta.json"
    if meta_path.exists():
        return load_profile_file(meta_path)
    return {}


def load_assignment_requirements(folder: Path) -> Dict[str, Any]:
    req_path = folder / "requirements.json"
    if req_path.exists():
        return load_profile_file(req_path)
    return {}


def _assignment_detail_fingerprint(folder: Path) -> Tuple[float, float, float]:
    meta_path = folder / "meta.json"
    req_path = folder / "requirements.json"
    q_path = folder / "questions.csv"
    def mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime if p.exists() else 0.0
        except Exception:
            _log.debug("file stat failed", exc_info=True)
            return 0.0
    return (mtime(meta_path), mtime(req_path), mtime(q_path))


def build_assignment_detail_cached(folder: Path, include_text: bool = True) -> Dict[str, Any]:
    from services.api import app_core as _ac
    if ASSIGNMENT_DETAIL_CACHE_TTL_SEC <= 0:
        return _ac.build_assignment_detail(folder, include_text=include_text)
    key = (str(folder), bool(include_text))
    now = time.monotonic()
    fp = _assignment_detail_fingerprint(folder)
    with _ASSIGNMENT_DETAIL_CACHE_LOCK:
        cached = _ASSIGNMENT_DETAIL_CACHE.get(key)
        if cached:
            ts, cached_fp, data = cached
            if (now - ts) <= ASSIGNMENT_DETAIL_CACHE_TTL_SEC and cached_fp == fp:
                return data
    data = _ac.build_assignment_detail(folder, include_text=include_text)
    with _ASSIGNMENT_DETAIL_CACHE_LOCK:
        _ASSIGNMENT_DETAIL_CACHE[key] = (now, fp, data)
    return data
