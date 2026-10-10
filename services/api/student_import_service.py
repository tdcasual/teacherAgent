from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class StudentImportDeps:
    app_root: Path
    data_dir: Path
    load_profile_file: Callable[[Path], Dict[str, Any]]
    now_iso: Callable[[], str]


def student_import(_args: Dict[str, Any], *, deps: StudentImportDeps) -> Dict[str, Any]:
    _ = deps
    return {"ok": False, "error": "gone", "status_code": 410}
