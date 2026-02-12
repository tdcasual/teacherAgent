from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException


def ensure_exam_ok(result: Dict[str, Any]) -> None:
    error = result.get("error")
    if not error:
        return
    if error == "exam_not_found":
        raise HTTPException(status_code=404, detail="exam not found")
    raise HTTPException(status_code=400, detail=result)
