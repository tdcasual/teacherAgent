from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class CoreServicesContract(Protocol):
    """Minimal service surface expected by route handlers and skill policies."""

    def allowed_tools(self, role: str) -> List[str]:
        ...

    def build_system_prompt(self, role: str, student_id: Optional[str] = None) -> str:
        ...

    def tool_dispatch(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        ...
