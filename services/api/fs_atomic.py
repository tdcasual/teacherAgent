from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable


def _atomic_tmp_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _atomic_tmp_path(path)
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def atomic_write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _atomic_tmp_path(path)
    try:
        with tmp.open("w", encoding="utf-8") as file_obj:
            for record in records:
                file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
