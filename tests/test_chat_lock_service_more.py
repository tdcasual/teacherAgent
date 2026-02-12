from __future__ import annotations

import json
from pathlib import Path

from services.api import chat_lock_service as cls


class _PathWithBadStat:
    def __init__(self, inner: Path):
        self._inner = inner
        self.parent = inner.parent

    def __str__(self) -> str:
        return str(self._inner)

    def unlink(self, *, missing_ok: bool = False) -> None:
        self._inner.unlink(missing_ok=missing_ok)

    def stat(self):
        raise OSError("stat failed")


class _BadUnlinkPath:
    def unlink(self, *, missing_ok: bool = False) -> None:  # pragma: no cover - invoked by test
        raise OSError("unlink failed")


def test_pid_alive_handles_non_positive_permission_and_generic(monkeypatch):
    assert cls._pid_alive(0) is False

    def _raise_permission(_pid: int, _sig: int) -> None:
        raise PermissionError

    def _raise_other(_pid: int, _sig: int) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(cls.os, "kill", _raise_permission)
    assert cls._pid_alive(123) is True

    monkeypatch.setattr(cls.os, "kill", _raise_other)
    assert cls._pid_alive(123) is True


def test_pid_alive_returns_true_when_kill_succeeds(monkeypatch):
    monkeypatch.setattr(cls.os, "kill", lambda _pid, _sig: None)
    assert cls._pid_alive(123) is True


def test_read_lock_pid_handles_non_dict_and_non_integer(tmp_path):
    list_payload = tmp_path / "list.lock"
    list_payload.write_text(json.dumps(["not", "dict"]), encoding="utf-8")
    assert cls._read_lock_pid(list_payload) == 0

    non_int_pid = tmp_path / "non_int.lock"
    non_int_pid.write_text(json.dumps({"pid": "abc"}), encoding="utf-8")
    assert cls._read_lock_pid(non_int_pid) == 0


def test_try_acquire_lockfile_handles_pid_check_exception(tmp_path, monkeypatch):
    path = tmp_path / "claim.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stale", encoding="utf-8")

    def _open_exists(_path: str, _flags: int) -> int:
        raise FileExistsError

    def _raise_in_read(_path: Path) -> int:
        raise RuntimeError("read failed")

    deps = cls.ChatLockDeps(
        now_ts=lambda: 1000.0,
        now_iso=lambda: "2026-01-01T00:00:00",
        get_pid=lambda: 321,
        os_open=_open_exists,
    )
    monkeypatch.setattr(cls, "_read_lock_pid", _raise_in_read)

    assert cls.try_acquire_lockfile(path, ttl_sec=0, deps=deps) is False


def test_try_acquire_lockfile_handles_ttl_stat_exception(tmp_path, monkeypatch):
    real_path = tmp_path / "claim.lock"
    real_path.parent.mkdir(parents=True, exist_ok=True)
    real_path.write_text("{}", encoding="utf-8")

    def _open_exists(_path: str, _flags: int) -> int:
        raise FileExistsError

    deps = cls.ChatLockDeps(
        now_ts=lambda: 1000.0,
        now_iso=lambda: "2026-01-01T00:00:00",
        get_pid=lambda: 321,
        os_open=_open_exists,
        is_pid_alive=lambda _pid: True,
    )
    monkeypatch.setattr(cls, "_read_lock_pid", lambda _path: 456)

    bad_path = _PathWithBadStat(real_path)
    assert cls.try_acquire_lockfile(bad_path, ttl_sec=10, deps=deps) is False


def test_try_acquire_lockfile_handles_unexpected_open_error(tmp_path):
    path = tmp_path / "claim.lock"

    def _open_raises(_path: str, _flags: int) -> int:
        raise RuntimeError("open failed")

    deps = cls.ChatLockDeps(
        now_ts=lambda: 1000.0,
        now_iso=lambda: "2026-01-01T00:00:00",
        get_pid=lambda: 1,
        os_open=_open_raises,
    )
    assert cls.try_acquire_lockfile(path, ttl_sec=10, deps=deps) is False


def test_try_acquire_lockfile_handles_close_error(tmp_path):
    path = tmp_path / "claim.lock"

    deps = cls.ChatLockDeps(
        now_ts=lambda: 1000.0,
        now_iso=lambda: "2026-01-01T00:00:00",
        get_pid=lambda: 1,
        os_open=lambda _path, _flags: 99,
        os_write=lambda _fd, _payload: 0,
        os_close=lambda _fd: (_ for _ in ()).throw(RuntimeError("close failed")),
    )

    assert cls.try_acquire_lockfile(path, ttl_sec=10, deps=deps) is True


def test_try_acquire_lockfile_exhausts_retries_when_stale_cleanup_loops(tmp_path, monkeypatch):
    path = tmp_path / "claim.lock"
    path.write_text("stale", encoding="utf-8")

    def _open_exists(_path: str, _flags: int) -> int:
        raise FileExistsError

    deps = cls.ChatLockDeps(
        now_ts=lambda: 1000.0,
        now_iso=lambda: "2026-01-01T00:00:00",
        get_pid=lambda: 1,
        os_open=_open_exists,
        is_pid_alive=lambda _pid: False,
    )
    monkeypatch.setattr(cls, "_read_lock_pid", lambda _path: 999)

    assert cls.try_acquire_lockfile(path, ttl_sec=10, deps=deps) is False


def test_release_lockfile_swallows_unlink_errors():
    cls.release_lockfile(_BadUnlinkPath())
