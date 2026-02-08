from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class StudentImportDeps:
    app_root: Path
    data_dir: Path
    load_profile_file: Callable[[Path], Dict[str, Any]]
    now_iso: Callable[[], str]


def _resolve_exam_manifest_path(data_dir: Path, exam_id: str) -> Optional[Path]:
    root = (data_dir / "exams").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        return None
    exam_dir = (root / eid).resolve()
    if exam_dir != root and root not in exam_dir.parents:
        return None
    return exam_dir / "manifest.json"


def _resolve_profile_path(profiles_dir: Path, student_id: str) -> Optional[Path]:
    root = profiles_dir.resolve()
    sid = str(student_id or "").strip()
    if not sid:
        return None
    target = (root / f"{sid}.json").resolve()
    if target != root and root not in target.parents:
        return None
    return target


def resolve_responses_file(
    exam_id: Optional[str],
    file_path: Optional[str],
    *,
    deps: StudentImportDeps,
) -> Optional[Path]:
    if file_path:
        path = Path(file_path)
        if not path.is_absolute():
            path = deps.app_root / path
        return path if path.exists() else None

    if exam_id:
        manifest_path = _resolve_exam_manifest_path(deps.data_dir, str(exam_id or ""))
        if manifest_path is None:
            return None
        if manifest_path.exists():
            manifest = deps.load_profile_file(manifest_path)
            files = manifest.get("files", {})
            resp_path = files.get("responses") or files.get("responses_scored") or files.get("responses_csv")
            if resp_path:
                candidate = Path(resp_path)
                if not candidate.is_absolute():
                    if str(resp_path).startswith("data/"):
                        candidate = deps.app_root / candidate
                    else:
                        candidate = deps.data_dir / candidate
                return candidate if candidate.exists() else None

    staging_dir = deps.data_dir / "staging"
    if staging_dir.exists():
        candidates = list(staging_dir.glob("*responses*scored*.csv"))
        if not candidates:
            candidates = list(staging_dir.glob("*responses*.csv"))
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]
    return None


def import_students_from_responses(
    path: Path,
    *,
    deps: StudentImportDeps,
    mode: str = "merge",
) -> Dict[str, Any]:
    if not path.exists():
        return {"error": f"responses file not found: {path}"}

    profiles_dir = deps.data_dir / "student_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    students: Dict[str, Dict[str, str]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            student_id = (row.get("student_id") or "").strip()
            student_name = (row.get("student_name") or "").strip()
            class_name = (row.get("class_name") or "").strip()
            exam_id = (row.get("exam_id") or "").strip()
            if not student_id:
                if class_name and student_name:
                    student_id = f"{class_name}_{student_name}"
                elif student_name:
                    student_id = student_name
            if not student_id:
                continue
            if student_id not in students:
                students[student_id] = {
                    "student_id": student_id,
                    "student_name": student_name,
                    "class_name": class_name,
                    "exam_id": exam_id,
                }

    created = 0
    updated = 0
    skipped = 0
    sample = []

    for student_id, info in students.items():
        profile_path = _resolve_profile_path(profiles_dir, student_id)
        if profile_path is None:
            skipped += 1
            continue
        profile = deps.load_profile_file(profile_path) if profile_path.exists() else {}
        is_new = not bool(profile)

        if is_new:
            created += 1
        else:
            updated += 1

        profile.setdefault("student_id", student_id)
        profile.setdefault("created_at", deps.now_iso())
        profile["last_updated"] = deps.now_iso()

        if info.get("student_name"):
            if not profile.get("student_name"):
                profile["student_name"] = info["student_name"]
            elif profile.get("student_name") != info["student_name"]:
                aliases = set(profile.get("aliases", []))
                aliases.add(info["student_name"])
                profile["aliases"] = sorted(aliases)

        if info.get("class_name") and not profile.get("class_name"):
            profile["class_name"] = info["class_name"]

        history = profile.get("import_history", [])
        history.append(
            {
                "timestamp": deps.now_iso(),
                "source": "exam_responses",
                "file": str(path),
                "exam_id": info.get("exam_id") or "",
                "mode": mode,
            }
        )
        profile["import_history"] = history[-10:]

        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        if len(sample) < 10:
            sample.append(student_id)

    total = len(students)
    if total == 0:
        skipped = 0
    return {
        "ok": True,
        "source_file": str(path),
        "total_students": total,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "sample": sample,
    }


def student_import(args: Dict[str, Any], *, deps: StudentImportDeps) -> Dict[str, Any]:
    source = args.get("source") or "responses_scored"
    exam_id = args.get("exam_id")
    file_path = args.get("file_path")
    mode = args.get("mode") or "merge"
    if source not in {"responses_scored", "responses"}:
        return {"error": f"unsupported source: {source}"}
    responses_path = resolve_responses_file(exam_id, file_path, deps=deps)
    if not responses_path:
        return {"error": "responses file not found", "exam_id": exam_id, "file_path": file_path}
    return import_students_from_responses(responses_path, deps=deps, mode=mode)
