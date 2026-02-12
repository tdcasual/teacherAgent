from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException

from ..api_models import AssignmentRequirementsRequest


@dataclass
class AssignmentHandlerDeps:
    list_assignments: Callable[[], Dict[str, Any]]
    compute_assignment_progress: Callable[[str, bool], Dict[str, Any]]
    parse_date_str: Callable[[Optional[str]], str]
    save_assignment_requirements: Callable[..., Dict[str, Any]]
    resolve_assignment_dir: Callable[[str], Path]
    load_assignment_requirements: Callable[[Path], Dict[str, Any]]
    assignment_today: Callable[..., Any]
    get_assignment_detail_api: Callable[[str], Dict[str, Any]]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def assignments(*, deps: AssignmentHandlerDeps) -> Any:
    return await _maybe_await(deps.list_assignments())


async def teacher_assignment_progress(
    assignment_id: str,
    *,
    include_students: bool = True,
    deps: AssignmentHandlerDeps,
) -> Any:
    assignment_id = (assignment_id or "").strip()
    if not assignment_id:
        raise HTTPException(status_code=400, detail="assignment_id is required")
    result = await _maybe_await(deps.compute_assignment_progress(assignment_id, bool(include_students)))
    if not result.get("ok") and result.get("error") == "assignment_not_found":
        raise HTTPException(status_code=404, detail="assignment not found")
    return result


async def teacher_assignments_progress(
    *,
    date: Optional[str] = None,
    deps: AssignmentHandlerDeps,
) -> Any:
    date_str = deps.parse_date_str(date)
    items = (await _maybe_await(deps.list_assignments())).get("assignments") or []
    out = []
    for it in items:
        if (it.get("date") or "") != date_str:
            continue
        aid = str(it.get("assignment_id") or "")
        if not aid:
            continue
        prog = await _maybe_await(deps.compute_assignment_progress(aid, False))
        if prog.get("ok"):
            out.append(prog)
    out.sort(key=lambda x: (x.get("updated_at") or ""), reverse=True)
    return {"ok": True, "date": date_str, "assignments": out}


async def assignment_requirements(
    req: AssignmentRequirementsRequest,
    *,
    deps: AssignmentHandlerDeps,
) -> Any:
    date_str = deps.parse_date_str(req.date)
    result = deps.save_assignment_requirements(
        req.assignment_id,
        req.requirements,
        date_str,
        created_by=req.created_by or "teacher",
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result


async def assignment_requirements_get(assignment_id: str, *, deps: AssignmentHandlerDeps) -> Any:
    try:
        folder = deps.resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not folder.exists():
        raise HTTPException(status_code=404, detail="assignment not found")
    requirements = deps.load_assignment_requirements(folder)
    if not requirements:
        return {"assignment_id": assignment_id, "requirements": None}
    return {"assignment_id": assignment_id, "requirements": requirements}


async def assignment_today(
    *,
    student_id: str,
    date: Optional[str],
    auto_generate: bool,
    generate: bool,
    per_kp: int,
    deps: AssignmentHandlerDeps,
) -> Any:
    return await _maybe_await(
        deps.assignment_today(
            student_id=student_id,
            date=date,
            auto_generate=auto_generate,
            generate=generate,
            per_kp=per_kp,
        )
    )


async def assignment_detail(assignment_id: str, *, deps: AssignmentHandlerDeps) -> Any:
    result = await _maybe_await(deps.get_assignment_detail_api(assignment_id))
    if result.get("error") == "assignment_not_found":
        raise HTTPException(status_code=404, detail="assignment not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result
