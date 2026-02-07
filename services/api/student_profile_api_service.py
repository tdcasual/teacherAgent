from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class StudentProfileApiDeps:
    student_profile_get: Callable[[str], Dict[str, Any]]


def get_profile_api(student_id: str, *, deps: StudentProfileApiDeps) -> Dict[str, Any]:
    return deps.student_profile_get(student_id)
