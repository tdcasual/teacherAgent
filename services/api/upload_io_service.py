from __future__ import annotations

from pathlib import Path


def sanitize_filename_io(name: str) -> str:
    return Path(str(name or "")).name
