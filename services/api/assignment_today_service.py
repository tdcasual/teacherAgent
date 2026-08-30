from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


class AssignmentTodayError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "assignment_today_error")


@dataclass(frozen=True)
class AssignmentTodayDeps:
    parse_date_str: Callable[[Optional[str]], str]
    list_student_today: Callable[[str, str], List[Dict[str, Any]]]


def assignment_today(
    *,
    student_id: str,
    date: Optional[str],
    auto_generate: bool,
    generate: bool,
    per_kp: int,
    deps: AssignmentTodayDeps,
) -> Dict[str, Any]:
    del generate, per_kp
    if auto_generate:
        raise AssignmentTodayError(400, "auto_generate_disabled")
    date_str = deps.parse_date_str(date)
    assignments = deps.list_student_today(str(student_id or "").strip(), date_str)
    return {"date": date_str, "assignments": assignments}
