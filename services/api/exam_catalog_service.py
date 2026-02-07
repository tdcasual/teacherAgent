from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class ExamCatalogDeps:
    data_dir: Path
    load_profile_file: Callable[[Path], Dict[str, Any]]


def list_exams(*, deps: ExamCatalogDeps) -> Dict[str, Any]:
    exams_dir = deps.data_dir / "exams"
    if not exams_dir.exists():
        return {"exams": []}

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
    return {"exams": items}
