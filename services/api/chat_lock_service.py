from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_log = logging.getLogger(__name__)


def _pid_alive(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        _log.debug("unexpected error checking pid %s, assuming alive", pid)
        return True
    return True


def _read_lock_pid(path: Path) -> int:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        payload = json.loads(raw)
    except Exception:
        _log.warning("failed to read/parse lock file %s", path, exc_info=True)
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        return int(payload.get("pid") or 0)
    except Exception:
        _log.debug("non-integer pid in lock file %s", path)
        return 0


@dataclass(frozen=True)
class ChatLockDeps:
    now_ts: Callable[[], float]
    now_iso: Callable[[], str]
    get_pid: Callable[[], int]
    os_open: Callable[[str, int], int] = os.open
    os_close: Callable[[int], None] = os.close
    os_write: Callable[[int, bytes], int] = os.write
    is_pid_alive: Callable[[int], bool] = _pid_alive


def try_acquire_lockfile(path: Path, ttl_sec: int, deps: ChatLockDeps) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = deps.now_ts()
    for _attempt in range(2):
        try:
            fd = deps.os_open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            pid = 0
            try:
                pid = _read_lock_pid(path)
            except Exception:
                _log.debug("failed to check/remove stale lock %s", path)
                pass
            if pid > 0:
                try:
                    if deps.is_pid_alive(pid):
                        return False
                except Exception:
                    _log.debug("failed to check pid liveness for %s", path)
                    return False
                try:
                    path.unlink(missing_ok=True)
                    continue
                except Exception:
                    _log.debug("failed to remove dead-pid lock %s", path)
                    return False
            try:
                age = now - float(path.stat().st_mtime)
                if ttl_sec > 0 and age > float(ttl_sec):
                    path.unlink(missing_ok=True)
                    continue
            except Exception:
                _log.debug("failed to check lock TTL for %s", path)
                pass
            return False
        except Exception:
            _log.warning("unexpected error acquiring lock %s", path, exc_info=True)
            return False
        try:
            payload = {"pid": deps.get_pid(), "ts": deps.now_iso()}
            deps.os_write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8", errors="ignore"))
        finally:
            try:
                deps.os_close(fd)
            except Exception:
                _log.debug("failed to close lock fd for %s", path)
                pass
        return True
    return False


def release_lockfile(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        _log.debug("failed to release lock file %s", path)
        pass


def chat_job_claim_path(job_id: str, chat_job_path: Callable[[str], Path]) -> Path:
    return chat_job_path(job_id) / "claim.lock"
