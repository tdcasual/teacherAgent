from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class AssignmentTodayDeps:
    data_dir: Path
    parse_date_str: Callable[[Optional[str]], str]
    has_llm_key: Callable[[], bool]
    load_profile_file: Callable[[Path], Dict[str, Any]]
    find_assignment_for_date: Callable[..., Optional[Dict[str, Any]]]
    derive_kp_from_profile: Callable[[Dict[str, Any]], List[str]]
    safe_assignment_id: Callable[[str, str], str]
    assignment_generate: Callable[[Dict[str, Any]], Dict[str, Any]]
    load_assignment_meta: Callable[[Path], Dict[str, Any]]
    build_assignment_detail: Callable[..., Dict[str, Any]]


def _resolve_student_profile_path(data_dir: Path, student_id: str) -> Optional[Path]:
    root = (data_dir / "student_profiles").resolve()
    sid = str(student_id or "").strip()
    if not sid:
        return None
    path = (root / f"{sid}.json").resolve()
    if path != root and root not in path.parents:
        return None
    return path


def _resolve_assignment_dir(data_dir: Path, assignment_id: str) -> Optional[Path]:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        return None
    path = (root / aid).resolve()
    if path != root and root not in path.parents:
        return None
    return path


def assignment_today(
    *,
    student_id: str,
    date: Optional[str],
    auto_generate: bool,
    generate: bool,
    per_kp: int,
    deps: AssignmentTodayDeps,
) -> Dict[str, Any]:
    date_str = deps.parse_date_str(date)
    generate_flag = bool(generate)
    if generate_flag and not deps.has_llm_key():
        generate_flag = False

    profile: Dict[str, Any] = {}
    class_name: Optional[str] = None
    if student_id:
        profile_path = _resolve_student_profile_path(deps.data_dir, student_id)
        if profile_path is not None:
            profile = deps.load_profile_file(profile_path)
            class_name = profile.get("class_name")

    found = deps.find_assignment_for_date(date_str, student_id=student_id, class_name=class_name)
    if not found and auto_generate:
        kp_list = deps.derive_kp_from_profile(profile)
        if not kp_list:
            kp_list = ["uncategorized"]
        assignment_id = deps.safe_assignment_id(student_id, date_str)
        args = {
            "assignment_id": assignment_id,
            "kp": ",".join(kp_list),
            "per_kp": per_kp,
            "generate": bool(generate_flag),
            "mode": "auto",
            "date": date_str,
            "student_ids": student_id,
            "class_name": class_name or "",
            "source": "auto",
        }
        deps.assignment_generate(args)
        folder = _resolve_assignment_dir(deps.data_dir, assignment_id)
        if folder is not None:
            found = {"folder": folder, "meta": deps.load_assignment_meta(folder)}

    if not found:
        return {"date": date_str, "assignment": None}

    detail = deps.build_assignment_detail(found["folder"], include_text=True)
    return {"date": date_str, "assignment": detail}
