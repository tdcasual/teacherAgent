from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class ContentCatalogDeps:
    data_dir: Path
    app_root: Path
    load_profile_file: Callable[[Path], Dict[str, Any]]
    load_skills: Callable[[Path], Any]


def list_lessons(*, deps: ContentCatalogDeps) -> Dict[str, Any]:
    lessons_dir = deps.data_dir / "lessons"
    if not lessons_dir.exists():
        return {"lessons": []}

    items = []
    for folder in lessons_dir.iterdir():
        if not folder.is_dir():
            continue
        lesson_id = folder.name
        summary = ""
        meta_path = folder / "lesson.json"
        if meta_path.exists():
            meta = deps.load_profile_file(meta_path)
            lesson_id = meta.get("lesson_id") or lesson_id
            summary = meta.get("summary", "")
        items.append({"lesson_id": lesson_id, "summary": summary})

    items.sort(key=lambda x: x.get("lesson_id") or "")
    return {"lessons": items}


def list_skills(*, deps: ContentCatalogDeps) -> Dict[str, Any]:
    skills_dir = deps.app_root / "skills"
    if not skills_dir.exists():
        return {"skills": []}

    loaded = deps.load_skills(skills_dir)
    items = [spec.as_public_dict() for spec in loaded.skills.values()]
    items.sort(key=lambda x: x.get("id") or "")
    payload: Dict[str, Any] = {"skills": items}
    if loaded.errors:
        payload["errors"] = [e.as_dict() for e in loaded.errors]
    return payload


def load_kp_catalog(data_dir: Path) -> Dict[str, Dict[str, str]]:
    path = data_dir / "knowledge" / "knowledge_points.csv"
    if not path.exists():
        return {}
    out: Dict[str, Dict[str, str]] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                kp_id = str(row.get("kp_id") or "").strip()
                if not kp_id:
                    continue
                out[kp_id] = {
                    "name": str(row.get("name") or "").strip(),
                    "status": str(row.get("status") or "").strip(),
                    "notes": str(row.get("notes") or "").strip(),
                }
    except Exception:
        return {}
    return out


def load_question_kp_map(data_dir: Path) -> Dict[str, str]:
    path = data_dir / "knowledge" / "knowledge_point_map.csv"
    if not path.exists():
        return {}
    out: Dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = str(row.get("question_id") or "").strip()
                kp_id = str(row.get("kp_id") or "").strip()
                if qid and kp_id:
                    out[qid] = kp_id
    except Exception:
        return {}
    return out
