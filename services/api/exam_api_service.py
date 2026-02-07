from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class ExamApiDeps:
    exam_get: Callable[[str], Dict[str, Any]]


def get_exam_detail_api(exam_id: str, *, deps: ExamApiDeps) -> Dict[str, Any]:
    return deps.exam_get(exam_id)
