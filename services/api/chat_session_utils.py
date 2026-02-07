from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


def resolve_student_session_id(
    student_id: str,
    assignment_id: Optional[str],
    assignment_date: Optional[str],
    *,
    parse_date_str: Callable[[Optional[str]], str],
) -> str:
    if assignment_id:
        return str(assignment_id)
    date_str = parse_date_str(assignment_date)
    return f"general_{date_str}"


def paginate_session_items(
    items: List[Dict[str, Any]],
    *,
    cursor: int,
    limit: int,
) -> Tuple[List[Dict[str, Any]], Optional[int], int]:
    total = len(items)
    start = max(0, int(cursor or 0))
    page_size = max(1, min(int(limit or 20), 100))
    if start >= total:
        return [], None, total
    end = min(total, start + page_size)
    next_cursor: Optional[int] = end if end < total else None
    return items[start:end], next_cursor, total
