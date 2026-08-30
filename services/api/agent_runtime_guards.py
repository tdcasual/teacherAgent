from __future__ import annotations

from typing import Any, Dict, List, Optional


def maybe_guard_teacher_subject_total(
    deps: Any,
    *,
    messages: List[Dict[str, Any]],
    last_user_text: str,
) -> Optional[Dict[str, Any]]:
    del deps, messages, last_user_text
    return None
