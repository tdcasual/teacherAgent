from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_DEFAULT_TIMEOUT_SEC = 120
_MAX_TIMEOUT_SEC = 3600
_DEFAULT_EXEC_RETRIES = 1
_MAX_EXEC_RETRIES = 6
_MAX_STD_CHARS = 60000
_MAX_PACKAGES = 24
_PREVIEWABLE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_run_id(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return text if _RUN_ID_RE.fullmatch(text) else None


def _safe_file_name(value: Any, default: str = "main.png") -> str:
    raw = str(value or "").strip()
    if not raw:
        return default
    name = Path(raw).name
    if not _FILE_RE.fullmatch(name):
        return default
    if not name.lower().endswith(".png"):
        name = f"{name}.png"
    return name


def _safe_any_file_name(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    name = Path(raw).name
    if not _FILE_RE.fullmatch(name):
        return None
    return name


def _format_artifacts_markdown(artifacts: List[Dict[str, Any]]) -> str:
    """Generate markdown for artifacts: inline preview for images, download link for others."""
    lines: List[str] = []
    for art in artifacts:
        name = str(art.get("name") or "")
        url = str(art.get("url") or "")
        if not name or not url:
            continue
        ext = Path(name).suffix.lower()
        if ext in _PREVIEWABLE_EXTS:
            lines.append(f"![{name}]({url})")
            lines.append(f"[下载 {name}]({url})")
        else:
            lines.append(f"[下载 {name}]({url})")
    return "\n\n".join(lines)


def _clip_text(value: str) -> str:
    if len(value) <= _MAX_STD_CHARS:
        return value
    return value[:_MAX_STD_CHARS] + "\n...[truncated]..."


def _normalize_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except Exception:  # policy: allowed-broad-except
        _log.debug("non-numeric timeout value %r, using default", value)
        return _DEFAULT_TIMEOUT_SEC
    if timeout <= 0:
        return _DEFAULT_TIMEOUT_SEC
    return min(timeout, _MAX_TIMEOUT_SEC)


def _normalize_retries(value: Any) -> int:
    try:
        retries = int(value)
    except Exception:  # policy: allowed-broad-except
        _log.debug("non-numeric retries value %r, using default", value)
        return _DEFAULT_EXEC_RETRIES
    if retries <= 0:
        return _DEFAULT_EXEC_RETRIES
    return min(retries, _MAX_EXEC_RETRIES)


def _normalize_bool(value: Any, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _normalize_packages(value: Any) -> List[str]:
    raw: List[str] = []
    if isinstance(value, list):
        raw = [str(x or "").strip() for x in value]
    elif isinstance(value, str):
        raw = [x.strip() for x in re.split(r"[,\s;；，]+", value) if x.strip()]
    out: List[str] = []
    for item in raw:
        pkg = item.strip()
        if not pkg:
            continue
        if not _PACKAGE_RE.fullmatch(pkg):
            continue
        key = pkg.lower()
        if key not in {x.lower() for x in out}:
            out.append(pkg)
        if len(out) >= _MAX_PACKAGES:
            break
    return out


def _extract_missing_module(stderr: str) -> Optional[str]:
    if not stderr:
        return None
    patterns = [
        r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]",
        r"ImportError:\s+No module named\s+([A-Za-z0-9_.-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, stderr)
        if not match:
            continue
        value = str(match.group(1) or "").strip().split(".")[0]
        if _PACKAGE_RE.fullmatch(value):
            return value
    return None

