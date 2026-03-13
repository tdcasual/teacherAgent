from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class StudentImportDeps:
    app_root: Path
    data_dir: Path
    load_profile_file: Callable[[Path], Dict[str, Any]]
    now_iso: Callable[[], str]


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
    except Exception:
        return False
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _path_allowed(path: Path, *, deps: StudentImportDeps) -> bool:
    return _path_within_root(path, deps.data_dir) or _path_within_root(path, deps.app_root)


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


def _resolve_existing_allowed_file(path: Path, *, deps: StudentImportDeps) -> Optional[Path]:
    try:
        resolved = path.resolve()
    except Exception:
        return None
    if not _path_allowed(resolved, deps=deps):
        return None
    return resolved if resolved.exists() and resolved.is_file() else None


def _resolve_direct_file(file_path: str, *, deps: StudentImportDeps) -> Optional[Path]:
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = deps.app_root / candidate
    return _resolve_existing_allowed_file(candidate, deps=deps)


def _resolve_manifest_file_candidate(resp_path: Any, *, deps: StudentImportDeps) -> Optional[Path]:
    if not resp_path:
        return None
    candidate = Path(str(resp_path))
    if not candidate.is_absolute():
        candidate = deps.app_root / candidate if str(resp_path).startswith("data/") else deps.data_dir / candidate
    return _resolve_existing_allowed_file(candidate, deps=deps)


def _resolve_from_exam_manifest(exam_id: str, *, deps: StudentImportDeps) -> Optional[Path]:
    manifest_path = _resolve_exam_manifest_path(deps.data_dir, exam_id)
    if manifest_path is None or not manifest_path.exists():
        return None
    manifest = deps.load_profile_file(manifest_path)
    files = manifest.get("files", {})
    resp_path = files.get("responses") or files.get("responses_scored") or files.get("responses_csv")
    return _resolve_manifest_file_candidate(resp_path, deps=deps)


def _latest_staging_responses_file(staging_dir: Path) -> Optional[Path]:
    if not staging_dir.exists():
        return None
    candidates = list(staging_dir.glob("*responses*scored*.csv")) or list(staging_dir.glob("*responses*.csv"))
    if not candidates:
        return None
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def resolve_responses_file(
    exam_id: Optional[str],
    file_path: Optional[str],
    *,
    deps: StudentImportDeps,
) -> Optional[Path]:
    if file_path:
        return _resolve_direct_file(file_path, deps=deps)

    if exam_id:
        from_manifest = _resolve_from_exam_manifest(str(exam_id or ""), deps=deps)
        if from_manifest is not None:
            return from_manifest

    return _latest_staging_responses_file(deps.data_dir / "staging")


def _student_id_from_row(row: Dict[str, str]) -> str:
    student_id = (row.get("student_id") or "").strip()
    student_name = (row.get("student_name") or "").strip()
    class_name = (row.get("class_name") or "").strip()
    if student_id:
        return student_id
    if class_name and student_name:
        return f"{class_name}_{student_name}"
    return student_name


def _collect_students(path: Path) -> Dict[str, Dict[str, str]]:
    students: Dict[str, Dict[str, str]] = {}
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            student_id = _student_id_from_row(row)
            if not student_id or student_id in students:
                continue
            students[student_id] = {
                "student_id": student_id,
                "student_name": (row.get("student_name") or "").strip(),
                "class_name": (row.get("class_name") or "").strip(),
                "exam_id": (row.get("exam_id") or "").strip(),
            }
    return students


def _merge_student_name(profile: Dict[str, Any], student_name: str) -> None:
    if not student_name:
        return
    if not profile.get("student_name"):
        profile["student_name"] = student_name
        return
    if profile.get("student_name") == student_name:
        return
    aliases = set(profile.get("aliases", []))
    aliases.add(student_name)
    profile["aliases"] = sorted(aliases)


def _append_import_history(
    profile: Dict[str, Any],
    *,
    path: Path,
    exam_id: str,
    mode: str,
    timestamp: str,
) -> None:
    history = profile.get("import_history", [])
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "timestamp": timestamp,
            "source": "exam_responses",
            "file": str(path),
            "exam_id": exam_id,
            "mode": mode,
        }
    )
    profile["import_history"] = history[-10:]


def _update_student_profile(
    profile: Dict[str, Any],
    *,
    student_id: str,
    info: Dict[str, str],
    path: Path,
    mode: str,
    timestamp: str,
) -> None:
    profile.setdefault("student_id", student_id)
    profile.setdefault("created_at", timestamp)
    profile["last_updated"] = timestamp
    _merge_student_name(profile, info.get("student_name", ""))
    if info.get("class_name") and not profile.get("class_name"):
        profile["class_name"] = info["class_name"]
    _append_import_history(profile, path=path, exam_id=info.get("exam_id", ""), mode=mode, timestamp=timestamp)


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
    students = _collect_students(path)

    created = 0
    updated = 0
    skipped = 0
    sample: List[str] = []

    for student_id, info in students.items():
        profile_path = _resolve_profile_path(profiles_dir, student_id)
        if profile_path is None:
            skipped += 1
            continue
        profile = deps.load_profile_file(profile_path) if profile_path.exists() else {}
        is_new = not bool(profile)
        timestamp = deps.now_iso()

        if is_new:
            created += 1
        else:
            updated += 1

        _update_student_profile(profile, student_id=student_id, info=info, path=path, mode=mode, timestamp=timestamp)
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
