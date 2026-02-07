from __future__ import annotations

from typing import Any, Callable, List, Optional


def resolve_role_hint(
    messages: List[Any],
    *,
    explicit_role: Optional[str],
    detect_role: Callable[[str], Optional[str]],
) -> Optional[str]:
    role_hint = explicit_role
    if role_hint and role_hint != "unknown":
        return role_hint
    for msg in reversed(messages or []):
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", "")
        if role == "user":
            detected = detect_role(str(content or ""))
            if detected:
                return detected
            break
    return role_hint
