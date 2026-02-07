from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class AssignmentApiDeps:
    build_assignment_detail: Callable[..., Dict[str, Any]]
    assignment_exists: Optional[Callable[[str], bool]] = None


def get_assignment_detail_api(assignment_id: str, *, deps: AssignmentApiDeps) -> Dict[str, Any]:
    if deps.assignment_exists is not None and not deps.assignment_exists(assignment_id):
        return {"error": "assignment_not_found"}
    return deps.build_assignment_detail(assignment_id, include_text=True)
