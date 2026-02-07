from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class TeacherMemoryApiDeps:
    resolve_teacher_id: Callable[[Optional[str]], str]
    teacher_memory_list_proposals: Callable[..., Dict[str, Any]]
    teacher_memory_apply: Callable[..., Dict[str, Any]]


def list_proposals_api(
    teacher_id: Optional[str],
    *,
    status: Optional[str],
    limit: int,
    deps: TeacherMemoryApiDeps,
) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    return deps.teacher_memory_list_proposals(teacher_id_final, status=status, limit=limit)


def review_proposal_api(
    proposal_id: str,
    *,
    teacher_id: Optional[str],
    approve: bool,
    deps: TeacherMemoryApiDeps,
) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    return deps.teacher_memory_apply(
        teacher_id_final,
        proposal_id=str(proposal_id or "").strip(),
        approve=bool(approve),
    )
