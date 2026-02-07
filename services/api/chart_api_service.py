from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class ChartApiDeps:
    chart_exec: Callable[[Dict[str, Any]], Dict[str, Any]]


def chart_exec_api(args: Dict[str, Any], *, deps: ChartApiDeps) -> Dict[str, Any]:
    return deps.chart_exec(args)
