from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class TeacherRoutingApiDeps:
    teacher_llm_routing_get: Callable[[Dict[str, Any]], Dict[str, Any]]


def get_routing_api(args: Dict[str, Any], *, deps: TeacherRoutingApiDeps) -> Dict[str, Any]:
    return deps.teacher_llm_routing_get(args)
