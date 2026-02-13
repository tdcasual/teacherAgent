"""General-purpose utility functions extracted from app_core.py.

Pure functions for text normalization, path resolution, scoring helpers, etc.
"""
from __future__ import annotations

import csv
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .config import APP_ROOT

_log = logging.getLogger(__name__)

__all__ = [
    "model_dump_compat",
    "run_script",
    "normalize",
    "parse_ids_value",
    "safe_slug",
    "resolve_scope",
    "normalize_due_at",
    "count_csv_rows",
    "_non_ws_len",
    "_percentile",
    "_score_band_label",
    "_SAFE_TOOL_ID_RE",
    "_is_safe_tool_id",
    "_resolve_app_path",
]


def model_dump_compat(model: Any, *, exclude_none: bool = False) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=exclude_none)
    return model.dict(exclude_none=exclude_none)


def run_script(args: List[str]) -> str:
    env = os.environ.copy()
    root = str(APP_ROOT)
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{root}{os.pathsep}{current}" if current else root
    timeout_raw = str(os.getenv("RUN_SCRIPT_TIMEOUT_SEC", "300") or "300").strip()
    try:
        timeout_sec = int(timeout_raw)
    except Exception:
        timeout_sec = 300
    timeout_sec = max(1, min(timeout_sec, 3600))
    proc = subprocess.run(args, capture_output=True, text=True, env=env, cwd=root, timeout=timeout_sec)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr or proc.stdout)
    return proc.stdout


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def parse_ids_value(value: Any) -> List[str]:
    from .assignment_requirements_service import parse_list_value as _parse_list_value_impl
    parts = _parse_list_value_impl(value)
    return [p for p in parts if p]


def safe_slug(value: str) -> str:
    return re.sub(r"[^\w-]+", "_", value or "").strip("_") or "assignment"


def resolve_scope(scope: str, student_ids: List[str], class_name: str) -> str:
    scope_norm = (scope or "").strip().lower()
    if scope_norm in {"public", "class", "student"}:
        return scope_norm
    if student_ids:
        return "student"
    if class_name:
        return "class"
    return "public"


def normalize_due_at(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw + "T23:59:59"
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return raw
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return None


def count_csv_rows(path: Path) -> int:
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            count = -1
            for count, _ in enumerate(reader):
                pass
        return max(count, 0)
    except Exception:
        _log.warning("failed to count CSV rows at %s", path, exc_info=True)
        return 0


def _non_ws_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    p = max(0.0, min(1.0, float(p)))
    idx = (len(sorted_vals) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    if lo == hi:
        return float(sorted_vals[lo])
    frac = idx - lo
    return float(sorted_vals[lo]) * (1.0 - frac) + float(sorted_vals[hi]) * frac


def _score_band_label(percent: float) -> str:
    p = max(0.0, min(100.0, float(percent)))
    if p >= 100.0:
        return "90–100%"
    start = int(p // 10) * 10
    end = 100 if start >= 90 else (start + 9)
    return f"{start}–{end}%"


_SAFE_TOOL_ID_RE = re.compile(r"^[^\x00/\\\\]+$")


def _is_safe_tool_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and bool(_SAFE_TOOL_ID_RE.match(text))


def _resolve_app_path(path_value: Any, must_exist: bool = True) -> Optional[Path]:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = (APP_ROOT / p).resolve()
    else:
        p = p.resolve()
    root = APP_ROOT.resolve()
    if root not in p.parents and p != root:
        return None
    if must_exist and not p.exists():
        return None
    return p
