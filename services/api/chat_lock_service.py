from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class ChatLockDeps:
    now_ts: Callable[[], float]
    now_iso: Callable[[], str]
    get_pid: Callable[[], int]
    os_open: Callable[[str, int], int] = os.open
    os_close: Callable[[int], None] = os.close
    os_write: Callable[[int, bytes], int] = os.write


def try_acquire_lockfile(path: Path, ttl_sec: int, deps: ChatLockDeps) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = deps.now_ts()
    for _attempt in range(2):
        try:
            fd = deps.os_open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = now - float(path.stat().st_mtime)
                if ttl_sec > 0 and age > float(ttl_sec):
                    path.unlink(missing_ok=True)
                    continue
            except Exception:
                pass
            return False
        except Exception:
            return False
        try:
            payload = {"pid": deps.get_pid(), "ts": deps.now_iso()}
            deps.os_write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8", errors="ignore"))
        finally:
            try:
                deps.os_close(fd)
            except Exception:
                pass
        return True
    return False


def release_lockfile(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def chat_job_claim_path(job_id: str, chat_job_path: Callable[[str], Path]) -> Path:
    return chat_job_path(job_id) / "claim.lock"
