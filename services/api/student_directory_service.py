from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class StudentDirectoryDeps:
    data_dir: Path
    load_profile_file: Callable[[Path], Dict[str, Any]]
    normalize: Callable[[str], str]


def student_search(query: str, limit: int, deps: StudentDirectoryDeps) -> Dict[str, Any]:
    profiles_dir = deps.data_dir / "student_profiles"
    if not profiles_dir.exists():
        return {"matches": []}

    q_norm = deps.normalize(query)
    matches = []
    for path in profiles_dir.glob("*.json"):
        profile = deps.load_profile_file(path)
        student_id = profile.get("student_id") or path.stem
        candidates = [
            student_id,
            profile.get("student_name", ""),
            profile.get("class_name", ""),
        ] + (profile.get("aliases") or [])

        best_score = 0.0
        for candidate in candidates:
            if not candidate:
                continue
            cand_norm = deps.normalize(str(candidate))
            if not cand_norm:
                continue
            if q_norm and q_norm in cand_norm:
                score = 1.0
            else:
                score = SequenceMatcher(None, q_norm, cand_norm).ratio() if q_norm else 0.0
            if score > best_score:
                best_score = score

        if best_score > 0.1:
            matches.append(
                {
                    "student_id": student_id,
                    "student_name": profile.get("student_name", ""),
                    "class_name": profile.get("class_name", ""),
                    "score": round(best_score, 3),
                }
            )

    matches.sort(key=lambda item: item["score"], reverse=True)
    return {"matches": matches[:limit]}


def student_candidates_by_name(name: str, deps: StudentDirectoryDeps) -> List[Dict[str, str]]:
    profiles_dir = deps.data_dir / "student_profiles"
    if not profiles_dir.exists():
        return []

    q_norm = deps.normalize(name)
    if not q_norm:
        return []

    results: List[Dict[str, str]] = []
    for path in profiles_dir.glob("*.json"):
        profile = deps.load_profile_file(path)
        student_id = profile.get("student_id") or path.stem
        student_name = profile.get("student_name", "")
        class_name = profile.get("class_name", "")
        aliases = profile.get("aliases") or []

        if q_norm in {
            deps.normalize(student_name),
            deps.normalize(student_id),
            deps.normalize(f"{class_name}{student_name}") if class_name and student_name else "",
        }:
            results.append(
                {
                    "student_id": student_id,
                    "student_name": student_name,
                    "class_name": class_name,
                }
            )
            continue

        matched_alias = False
        for alias in aliases:
            if q_norm == deps.normalize(alias):
                matched_alias = True
                break
        if matched_alias:
            results.append(
                {
                    "student_id": student_id,
                    "student_name": student_name,
                    "class_name": class_name,
                }
            )

    return results


def list_all_student_profiles(deps: StudentDirectoryDeps) -> List[Dict[str, str]]:
    profiles_dir = deps.data_dir / "student_profiles"
    if not profiles_dir.exists():
        return []

    out: List[Dict[str, str]] = []
    seen: set[str] = set()
    for path in profiles_dir.glob("*.json"):
        profile = deps.load_profile_file(path)
        student_id = str(profile.get("student_id") or path.stem).strip()
        if not student_id or student_id in seen:
            continue
        seen.add(student_id)
        out.append(
            {
                "student_id": student_id,
                "student_name": str(profile.get("student_name") or ""),
                "class_name": str(profile.get("class_name") or ""),
            }
        )

    return out


def list_all_student_ids(deps: StudentDirectoryDeps) -> List[str]:
    return sorted([item.get("student_id") for item in list_all_student_profiles(deps) if item.get("student_id")])


def list_student_ids_by_class(class_name: str, deps: StudentDirectoryDeps) -> List[str]:
    class_norm = deps.normalize(class_name or "")
    if not class_norm:
        return []

    out: List[str] = []
    for profile in list_all_student_profiles(deps):
        if deps.normalize(profile.get("class_name") or "") == class_norm and profile.get("student_id"):
            out.append(profile["student_id"])
    out.sort()
    return out
