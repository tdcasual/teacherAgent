from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable

_log = logging.getLogger(__name__)


def _atomic_tmp_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _atomic_tmp_path(path)
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        try:
            os.write(fd, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            _log.debug("failed to clean up temp file %s", tmp)
            pass


def atomic_write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _atomic_tmp_path(path)
    try:
        with tmp.open("w", encoding="utf-8") as file_obj:
            for record in records:
                file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")
            file_obj.flush()
            os.fsync(file_obj.fileno())
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            _log.debug("failed to clean up temp file %s", tmp)
            pass
