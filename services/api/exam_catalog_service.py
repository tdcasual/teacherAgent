from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

_DEFAULT_LIST_LIMIT = 50
_MAX_LIST_LIMIT = 100


@dataclass(frozen=True)
class ExamCatalogDeps:
    data_dir: Path
    load_profile_file: Callable[[Path], Dict[str, Any]]


def _normalize_paging(limit: Any, cursor: Any) -> tuple[int, int]:
    try:
        limit_int = int(limit)
    except Exception:
        limit_int = _DEFAULT_LIST_LIMIT
    try:
        cursor_int = int(cursor)
    except Exception:
        cursor_int = 0
    if limit_int <= 0:
        limit_int = _DEFAULT_LIST_LIMIT
    limit_int = min(limit_int, _MAX_LIST_LIMIT)
    cursor_int = max(0, cursor_int)
    return limit_int, cursor_int


def list_exams(*, limit: Any = _DEFAULT_LIST_LIMIT, cursor: Any = 0, deps: ExamCatalogDeps) -> Dict[str, Any]:
    limit_int, cursor_int = _normalize_paging(limit, cursor)
    exams_dir = deps.data_dir / "exams"
    if not exams_dir.exists():
        return {
            "exams": [],
            "total": 0,
            "limit": limit_int,
            "cursor": cursor_int,
            "has_more": False,
        }

    items = []
    for folder in exams_dir.iterdir():
        if not folder.is_dir():
            continue
        manifest_path = folder / "manifest.json"
        data = deps.load_profile_file(manifest_path) if manifest_path.exists() else {}
        exam_id = data.get("exam_id") or folder.name
        generated_at = data.get("generated_at")
        counts = data.get("counts", {})
        items.append(
            {
                "exam_id": exam_id,
                "generated_at": generated_at,
                "students": counts.get("students"),
                "responses": counts.get("responses"),
            }
        )

    items.sort(key=lambda x: x.get("generated_at") or "", reverse=True)
    total = len(items)
    page = items[cursor_int : cursor_int + limit_int]
    next_cursor = cursor_int + len(page)
    return {
        "exams": page,
        "total": total,
        "limit": limit_int,
        "cursor": cursor_int,
        "next_cursor": next_cursor if next_cursor < total else None,
        "has_more": next_cursor < total,
    }
