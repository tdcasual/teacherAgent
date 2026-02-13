from __future__ import annotations

import errno
import fcntl
import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _HeldLock:
    fd: int
    owner: str


_HELD_LOCKS: Dict[str, _HeldLock] = {}
_HELD_LOCKS_GUARD = threading.Lock()


def _path_key(path: Path) -> str:
    try:
        return str(Path(str(path)).resolve())
    except Exception:
        return str(path)


def _get_held_lock(path: Path) -> Optional[_HeldLock]:
    key = _path_key(path)
    with _HELD_LOCKS_GUARD:
        return _HELD_LOCKS.get(key)


def _register_held_lock(path: Path, fd: int, owner: str) -> bool:
    key = _path_key(path)
    with _HELD_LOCKS_GUARD:
        if key in _HELD_LOCKS:
            return False
        _HELD_LOCKS[key] = _HeldLock(fd=fd, owner=owner)
        return True


def _pop_held_lock(path: Path) -> Optional[_HeldLock]:
    key = _path_key(path)
    with _HELD_LOCKS_GUARD:
        return _HELD_LOCKS.pop(key, None)


def _best_effort_flock(fd: int, op: int) -> bool:
    try:
        fcntl.flock(fd, op)
        return True
    except OSError as exc:
        if exc.errno in {errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES}:
            return False
        _log.debug("flock failed for fd=%s op=%s", fd, op, exc_info=True)
        return False
    except Exception:
        _log.debug("flock failed for fd=%s op=%s", fd, op, exc_info=True)
        return False


def _read_lock_payload(path: Path) -> Dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except Exception:
        _log.debug("failed to read lock payload %s", path, exc_info=True)
    return {}


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
    payload = _read_lock_payload(path)
    if not payload:
        _log.warning("failed to read/parse lock file %s", path, exc_info=True)
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
    if _get_held_lock(path) is not None:
        return False
    now = deps.now_ts()
    for _attempt in range(2):
        try:
            fd = deps.os_open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _get_held_lock(path) is not None:
                return False

            probe_fd: Optional[int] = None
            try:
                probe_fd = os.open(str(path), os.O_RDWR)
                if not _best_effort_flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB):
                    return False
            except FileNotFoundError:
                continue
            except Exception:
                _log.debug("failed to probe existing lock file %s", path, exc_info=True)
            finally:
                if probe_fd is not None:
                    _best_effort_flock(probe_fd, fcntl.LOCK_UN)
                    try:
                        os.close(probe_fd)
                    except Exception:
                        _log.debug("failed to close probe fd for %s", path)

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
        owner = uuid.uuid4().hex
        try:
            payload = {"pid": deps.get_pid(), "ts": deps.now_iso(), "owner": owner}
            deps.os_write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8", errors="ignore"))
            # Keep descriptor open for the lock lifetime; best-effort flock adds
            # cross-process contention signal without changing lockfile contract.
            _best_effort_flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not _register_held_lock(path, fd, owner):
                raise RuntimeError("lock_already_held_locally")
            return True
        except Exception:
            _log.debug("failed to persist lock payload for %s", path, exc_info=True)
            _best_effort_flock(fd, fcntl.LOCK_UN)
            try:
                deps.os_close(fd)
            except Exception:
                _log.debug("failed to close lock fd for %s", path)
                pass
            try:
                path.unlink(missing_ok=True)
            except Exception:
                _log.debug("failed to cleanup partial lock %s", path)
            return False
    return False


def release_lockfile(path: Path) -> None:
    held = _pop_held_lock(path)
    if held is not None:
        try:
            payload = _read_lock_payload(path)
            owner = str(payload.get("owner") or "").strip()
            # Only remove lockfile if owner still matches; avoids deleting a lock
            # recreated by another process after stale recovery.
            if not owner or owner == held.owner:
                path.unlink(missing_ok=True)
        except Exception:
            _log.debug("failed to release owned lock file %s", path, exc_info=True)
        finally:
            _best_effort_flock(held.fd, fcntl.LOCK_UN)
            try:
                os.close(held.fd)
            except Exception:
                _log.debug("failed to close owned lock fd for %s", path)
        return
    try:
        path.unlink(missing_ok=True)
    except Exception:
        _log.debug("failed to release lock file %s", path)
        pass


def chat_job_claim_path(job_id: str, chat_job_path: Callable[[str], Path]) -> Path:
    return chat_job_path(job_id) / "claim.lock"
