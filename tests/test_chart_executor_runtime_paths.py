from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from services.api import chart_executor as ce
from services.api import chart_sandbox, global_limits


class _FakeSemaphore:
    def __init__(self, acquire_result: bool) -> None:
        self.acquire_result = acquire_result
        self.acquire_calls = 0
        self.release_calls = 0

    def acquire(self, timeout: int = 30) -> bool:
        self.acquire_calls += 1
        self.timeout = timeout
        return self.acquire_result

    def release(self) -> None:
        self.release_calls += 1


def _set_fixed_uuid(monkeypatch: pytest.MonkeyPatch, hex_value: str) -> str:
    monkeypatch.setattr(ce.uuid, "uuid4", lambda: SimpleNamespace(hex=hex_value))
    return f"chr_{hex_value[:12]}"


def _patch_inner_sandbox(monkeypatch: pytest.MonkeyPatch, *, guard_source: str = "") -> None:
    monkeypatch.setattr(chart_sandbox, "build_filesystem_guard_source", lambda *_args, **_kwargs: guard_source)
    monkeypatch.setattr(chart_sandbox, "build_sanitized_env", lambda profile: {"SAFE": "1", "PROFILE": profile})
    monkeypatch.setattr(chart_sandbox, "make_preexec_fn", lambda profile, timeout_sec: None)


def test_execute_chart_exec_returns_missing_python_code(tmp_path: Path) -> None:
    out = ce.execute_chart_exec({}, tmp_path, tmp_path / "uploads")
    assert out == {"error": "missing_python_code"}


def test_execute_chart_exec_sandbox_short_circuits_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chart_sandbox, "scan_code_patterns", lambda code, profile: {"error": "blocked"})

    out = ce.execute_chart_exec(
        {"python_code": "print(1)", "execution_profile": "sandboxed"},
        tmp_path,
        tmp_path / "uploads",
    )
    assert out == {"error": "blocked"}


def test_execute_chart_exec_returns_busy_when_semaphore_not_acquired(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chart_sandbox, "scan_code_patterns", lambda code, profile: None)
    sem = _FakeSemaphore(acquire_result=False)
    monkeypatch.setattr(global_limits, "GLOBAL_CHART_EXEC_SEMAPHORE", sem)

    out = ce.execute_chart_exec({"python_code": "print(1)"}, tmp_path, tmp_path / "uploads")

    assert out["error"] == "chart_exec_busy"
    assert sem.acquire_calls == 1
    assert sem.release_calls == 0


def test_execute_chart_exec_releases_semaphore_on_inner_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chart_sandbox, "scan_code_patterns", lambda code, profile: None)
    sem = _FakeSemaphore(acquire_result=True)
    monkeypatch.setattr(global_limits, "GLOBAL_CHART_EXEC_SEMAPHORE", sem)
    monkeypatch.setattr(
        ce,
        "_execute_chart_exec_inner",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("inner failed")),
    )

    with pytest.raises(RuntimeError, match="inner failed"):
        ce.execute_chart_exec({"python_code": "print(1)"}, tmp_path, tmp_path / "uploads")

    assert sem.acquire_calls == 1
    assert sem.release_calls == 1


def test_execute_chart_exec_invalid_profile_falls_back_to_trusted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chart_sandbox, "scan_code_patterns", lambda code, profile: None)
    sem = _FakeSemaphore(acquire_result=True)
    monkeypatch.setattr(global_limits, "GLOBAL_CHART_EXEC_SEMAPHORE", sem)

    captured: Dict[str, Any] = {}

    def _fake_inner(args: Dict[str, Any], app_root: Path, uploads_dir: Path, python_code: str, execution_profile: str) -> Dict[str, Any]:
        captured["execution_profile"] = execution_profile
        captured["python_code"] = python_code
        return {"ok": True, "profile": execution_profile}

    monkeypatch.setattr(ce, "_execute_chart_exec_inner", _fake_inner)

    out = ce.execute_chart_exec(
        {"python_code": "print(1)", "execution_profile": "invalid-profile"},
        tmp_path,
        tmp_path / "uploads",
    )

    assert out["ok"] is True
    assert captured["execution_profile"] == "trusted"
    assert sem.release_calls == 1


def test_execute_chart_exec_inner_venv_init_failed_writes_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_root = tmp_path / "app"
    uploads_dir = tmp_path / "uploads"
    app_root.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)
    run_id = _set_fixed_uuid(monkeypatch, "b" * 32)
    _patch_inner_sandbox(monkeypatch)

    monkeypatch.setattr(ce, "_maybe_prune_chart_envs", lambda *_args, **_kwargs: {"enabled": True})
    monkeypatch.setattr(ce, "_ensure_venv", lambda env_dir: {"ok": False, "error": "venv failed"})
    monkeypatch.setattr(ce, "_mark_chart_env_used", lambda *_args, **_kwargs: None)

    out = ce._execute_chart_exec_inner(
        {"python_code": "print(1)", "auto_install": True, "packages": ["numpy"]},
        app_root,
        uploads_dir,
        "print(1)",
        "trusted",
    )

    meta = json.loads((uploads_dir / "chart_runs" / run_id / "meta.json").read_text(encoding="utf-8"))
    assert out["error"] == "venv_init_failed"
    assert meta["ok"] is False
    assert meta["run_id"] == run_id


def test_execute_chart_exec_inner_auto_install_retrys_missing_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_root = tmp_path / "app"
    uploads_dir = tmp_path / "uploads"
    app_root.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)
    run_id = _set_fixed_uuid(monkeypatch, "c" * 32)
    _patch_inner_sandbox(monkeypatch)

    monkeypatch.setattr(ce, "_maybe_prune_chart_envs", lambda *_args, **_kwargs: {"enabled": True})
    monkeypatch.setattr(ce, "_ensure_venv", lambda env_dir: {"ok": True, "python": "python3"})
    monkeypatch.setattr(ce, "_mark_chart_env_used", lambda *_args, **_kwargs: None)

    def _acquire(env_dir: Path, _run_id: str) -> Path:
        lease = env_dir / ".lease_test"
        lease.parent.mkdir(parents=True, exist_ok=True)
        lease.write_text("lease", encoding="utf-8")
        return lease

    released: List[Path] = []
    monkeypatch.setattr(ce, "_acquire_chart_env_lease", _acquire)
    monkeypatch.setattr(ce, "_release_chart_env_lease", lambda path: released.append(path) if path else None)

    pip_calls: List[List[str]] = []

    def _pip_install(_python: str, packages: List[str], timeout_sec: int) -> Dict[str, Any]:
        pip_calls.append(list(packages))
        return {"ok": True, "packages": list(packages), "exit_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(ce, "_pip_install", _pip_install)

    run_counter = {"value": 0}

    def _subprocess_run(*args: Any, **kwargs: Any) -> Any:
        run_counter["value"] += 1
        if run_counter["value"] == 1:
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'seaborn'",
            )

        image = uploads_dir / "charts" / run_id / "main.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"\x89PNG\r\n")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(ce.subprocess, "run", _subprocess_run)

    out = ce._execute_chart_exec_inner(
        {
            "python_code": "print(1)",
            "auto_install": True,
            "max_retries": 2,
        },
        app_root,
        uploads_dir,
        "print(1)",
        "trusted",
    )

    assert out["ok"] is True
    assert out["installed_packages"] == ["seaborn"]
    assert len(out["attempts"]) == 2
    assert ["seaborn"] in pip_calls
    assert out["attempts"][0]["exit_code"] == 1
    assert out["attempts"][1]["exit_code"] == 0
    assert released and isinstance(released[0], Path)


def test_execute_chart_exec_inner_timeout_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_root = tmp_path / "app"
    uploads_dir = tmp_path / "uploads"
    app_root.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)
    _set_fixed_uuid(monkeypatch, "d" * 32)
    _patch_inner_sandbox(monkeypatch)

    def _raise_timeout(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(
            cmd=["python3", "run.py"],
            timeout=2,
            output="partial-stdout",
            stderr="partial-stderr",
        )

    monkeypatch.setattr(ce.subprocess, "run", _raise_timeout)

    out = ce._execute_chart_exec_inner(
        {
            "python_code": "print(1)",
            "timeout_sec": 2,
            "max_retries": 1,
        },
        app_root,
        uploads_dir,
        "print(1)",
        "trusted",
    )

    assert out["ok"] is False
    assert out["timed_out"] is True
    assert out["exit_code"] == -1
    assert "process timed out" in out["stderr"]
    assert out["attempts"][0]["timed_out"] is True


def test_execute_chart_exec_inner_sandbox_injects_fs_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_root = tmp_path / "app"
    uploads_dir = tmp_path / "uploads"
    app_root.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)
    run_id = _set_fixed_uuid(monkeypatch, "e" * 32)

    guard_calls: Dict[str, Any] = {}

    def _guard(output_dir: str, allowed_roots: List[str]) -> str:
        guard_calls["output_dir"] = output_dir
        guard_calls["allowed_roots"] = allowed_roots
        return "# GUARD"

    monkeypatch.setattr(chart_sandbox, "build_filesystem_guard_source", _guard)
    monkeypatch.setattr(chart_sandbox, "build_sanitized_env", lambda profile: {"PROFILE": profile})
    monkeypatch.setattr(chart_sandbox, "make_preexec_fn", lambda profile, timeout_sec: None)

    def _run(*args: Any, **kwargs: Any) -> Any:
        image = uploads_dir / "charts" / run_id / "main.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"\x89PNG\r\n")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ce.subprocess, "run", _run)

    out = ce._execute_chart_exec_inner(
        {"python_code": "print(1)"},
        app_root,
        uploads_dir,
        "print(1)",
        "sandboxed",
    )

    script_text = (uploads_dir / "chart_runs" / run_id / "run.py").read_text(encoding="utf-8")
    assert out["ok"] is True
    assert script_text.startswith("# GUARD\n")
    assert guard_calls["output_dir"].endswith(f"charts/{run_id}")
    assert str(uploads_dir) in guard_calls["allowed_roots"]
    assert str(uploads_dir.parent / "data") in guard_calls["allowed_roots"]


def test_execute_chart_exec_inner_error_branches_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_root = tmp_path / "app"
    uploads_dir = tmp_path / "uploads"
    app_root.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)
    (app_root / "new.txt").write_text("new", encoding="utf-8")
    run_id = _set_fixed_uuid(monkeypatch, "f" * 32)
    _patch_inner_sandbox(monkeypatch)

    monkeypatch.setattr(ce, "_maybe_prune_chart_envs", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("gc boom")))
    monkeypatch.setattr(ce, "_ensure_venv", lambda env_dir: {"ok": True, "python": "python3"})
    monkeypatch.setattr(ce, "_mark_chart_env_used", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("mark boom")))
    monkeypatch.setattr(
        ce,
        "_acquire_chart_env_lease",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("lease boom")),
    )
    monkeypatch.setattr(
        ce,
        "_pip_install",
        lambda *_args, **_kwargs: {"ok": True, "packages": ["numpy"], "exit_code": 0, "stdout": "", "stderr": ""},
    )

    scandir_calls = {"value": 0}
    orig_scandir = ce.os.scandir

    def _scandir(path: str) -> Any:
        scandir_calls["value"] += 1
        if scandir_calls["value"] == 1:
            raise OSError("snapshot failed")
        return orig_scandir(path)

    monkeypatch.setattr(ce.os, "scandir", _scandir)
    monkeypatch.setattr(ce.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("run boom")))
    monkeypatch.setattr(ce.shutil, "copy2", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy boom")))

    out = ce._execute_chart_exec_inner(
        {
            "python_code": "print(1)",
            "auto_install": True,
            "packages": ["numpy"],
            "max_retries": 1,
        },
        app_root,
        uploads_dir,
        "print(1)",
        "trusted",
    )

    assert out["ok"] is False
    assert out["env_gc"]["error"] == "gc_failed"
    assert out["attempts"][0]["exit_code"] == -1
    assert "run boom" in out["stderr"]
    meta = json.loads((uploads_dir / "chart_runs" / run_id / "meta.json").read_text(encoding="utf-8"))
    assert meta["run_id"] == run_id


def test_prune_and_maybe_prune_edge_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploads_dir = tmp_path / "uploads"

    # _prune_chart_envs disabled branch.
    disabled = ce._prune_chart_envs(
        uploads_dir,
        keep_scopes=set(),
        policy={"enabled": False},
        now_ts=100.0,
    )
    assert disabled["enabled"] is False
    assert disabled["skipped"] == "disabled"

    # _prune_chart_envs delete failure branch.
    env_dir = uploads_dir / "chart_envs" / "pkg_old"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "payload.bin").write_bytes(b"x")

    monkeypatch.setattr(ce, "_delete_chart_env_dir", lambda item: "delete-failed")
    failed = ce._prune_chart_envs(
        uploads_dir,
        keep_scopes=set(),
        policy={
            "enabled": True,
            "ttl_sec": 1,
            "min_keep": 0,
            "max_keep": 10,
            "max_total_bytes": 1 << 50,
            "active_grace_sec": 0,
            "lease_ttl_sec": 60,
        },
        now_ts=time.time() + 10000,
    )
    assert failed["failed"]

    # _maybe_prune_chart_envs disabled branch.
    maybe_disabled = ce._maybe_prune_chart_envs(uploads_dir, keep_scopes=set(), policy={"enabled": False})
    assert maybe_disabled["skipped"] == "disabled"

    # _maybe_prune_chart_envs interval branch.
    state_path = ce._env_gc_state_path(uploads_dir / "chart_envs")
    ce._write_json_dict(state_path, {"last_gc_ts": 950.0})
    monkeypatch.setattr(ce.time, "time", lambda: 1000.0)
    maybe_interval = ce._maybe_prune_chart_envs(
        uploads_dir,
        keep_scopes=set(),
        policy={"enabled": True, "interval_sec": 100},
    )
    assert maybe_interval["skipped"] == "interval"
    assert maybe_interval["next_gc_ts"] == 1050.0

    # _maybe_prune_chart_envs write-state failure branch.
    monkeypatch.setattr(ce, "_prune_chart_envs", lambda *_args, **_kwargs: {"enabled": True, "deleted_scopes": []})
    monkeypatch.setattr(ce, "_write_json_dict", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("io")))
    report = ce._maybe_prune_chart_envs(
        uploads_dir,
        keep_scopes=set(),
        policy={"enabled": True, "interval_sec": 0},
    )
    assert report["enabled"] is True
    assert report["last_gc_ts"] == 1000.0


def test_helper_error_branches_for_json_env_lease_and_scandir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # _read_json_dict parse failure path.
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{oops", encoding="utf-8")
    assert ce._read_json_dict(bad_json) == {}

    # _env_int non-numeric and max-clamp paths.
    monkeypatch.setenv("CE_TEST_ENV_INT", "not-int")
    assert ce._env_int("CE_TEST_ENV_INT", default=7, minimum=1, maximum=10) == 7
    monkeypatch.setenv("CE_TEST_ENV_INT", "999")
    assert ce._env_int("CE_TEST_ENV_INT", default=7, minimum=1, maximum=10) == 10

    assert ce._numeric_ts(0) is None
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    assert ce._env_last_used_ts(env_dir, {"last_used_ts": 123.0}) == 123.0

    orig_stat = Path.stat

    def _raise_stat(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == env_dir:
            raise OSError("stat failed")
        return orig_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _raise_stat)
    assert ce._env_last_used_ts(env_dir, {}) == 0.0
    monkeypatch.setattr(Path, "stat", orig_stat)

    # _mark_chart_env_used utime failure branch.
    monkeypatch.setattr(ce.os, "utime", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("utime failed")))
    ce._mark_chart_env_used(env_dir, scope="x", packages=["numpy"], now_ts=10.0)
    meta = json.loads((env_dir / ".env_meta.json").read_text(encoding="utf-8"))
    assert meta["scope"] == "x"

    # lease helpers and release exception branch.
    lease_path = ce._env_lease_path(env_dir, "run/with bad chars")
    assert lease_path.name.startswith(".lease_run_with_bad_chars")
    acquired = ce._acquire_chart_env_lease(env_dir, "run1")
    assert acquired.exists()
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=True: (_ for _ in ()).throw(OSError("unlink fail")))
    ce._release_chart_env_lease(acquired)

    # cleanup stale lease branches (stat fail + unlink fail)
    bad_stat = env_dir / ".lease_badstat"
    bad_unlink = env_dir / ".lease_badunlink"
    bad_stat.write_text("x", encoding="utf-8")
    bad_unlink.write_text("x", encoding="utf-8")

    orig_stat2 = Path.stat
    orig_unlink = Path.unlink

    def _stat_for_cleanup(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == ".lease_badstat":
            raise OSError("stat bad")
        return orig_stat2(path, *args, **kwargs)

    def _unlink_for_cleanup(path: Path, missing_ok: bool = True) -> None:
        if path.name == ".lease_badunlink":
            raise OSError("unlink bad")
        return orig_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "stat", _stat_for_cleanup)
    monkeypatch.setattr(Path, "unlink", _unlink_for_cleanup)
    ce._cleanup_stale_chart_env_leases(env_dir, now_ts=time.time() + 99999, lease_ttl_sec=1)

    # _has_active_chart_env_lease exception path.
    monkeypatch.setattr(Path, "glob", lambda self, pattern: (_ for _ in ()).throw(OSError("glob bad")))
    assert ce._has_active_chart_env_lease(env_dir) is False

    # _dir_size_bytes entry and scan exception branches.
    class _FakeEntry:
        path = "x"

        def is_symlink(self) -> bool:
            return False

        def is_dir(self, follow_symlinks: bool = False) -> bool:
            return False

        def is_file(self, follow_symlinks: bool = False) -> bool:
            raise OSError("entry bad")

    class _FakeScan:
        def __enter__(self) -> List[_FakeEntry]:
            return [_FakeEntry()]

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(ce.os, "scandir", lambda _path: _FakeScan())
    assert ce._dir_size_bytes(env_dir) == 0
    monkeypatch.setattr(ce.os, "scandir", lambda _path: (_ for _ in ()).throw(OSError("scan bad")))
    assert ce._dir_size_bytes(env_dir) == 0

    # _delete_chart_env_dir exception path.
    target = tmp_path / "cannot-delete"
    target.mkdir(parents=True)
    monkeypatch.setattr(ce.shutil, "rmtree", lambda _path: (_ for _ in ()).throw(OSError("rm bad")))
    assert "rm bad" in (ce._delete_chart_env_dir({"path": target}) or "")


def test_ensure_venv_and_pip_install_error_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_dir = tmp_path / "env"

    # Existing python path shortcut.
    py = env_dir / "bin" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    ok = ce._ensure_venv(env_dir)
    assert ok["ok"] is True

    # subprocess exception.
    monkeypatch.setattr(ce.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    err = ce._ensure_venv(tmp_path / "env_err")
    assert err["ok"] is False
    assert "boom" in err["error"]

    # subprocess non-zero.
    monkeypatch.setattr(
        ce.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="o", stderr="e"),
    )
    bad = ce._ensure_venv(tmp_path / "env_bad")
    assert bad["error"] == "venv_create_failed"

    # subprocess zero but python still missing.
    monkeypatch.setattr(
        ce.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    missing = ce._ensure_venv(tmp_path / "env_missing")
    assert missing["error"] == "venv_python_missing"

    # subprocess success and python created afterwards.
    env_ok = tmp_path / "env_ok"

    def _run_and_create(*args: Any, **kwargs: Any) -> Any:
        py_path = env_ok / "bin" / "python"
        py_path.parent.mkdir(parents=True, exist_ok=True)
        py_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ce.subprocess, "run", _run_and_create)
    created = ce._ensure_venv(env_ok)
    assert created["ok"] is True

    # _pip_install no packages.
    assert ce._pip_install("python3", [], timeout_sec=10) == {"ok": True, "packages": []}

    # _pip_install timeout.
    def _pip_timeout(*_args: Any, **_kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="pip", timeout=10, output="x", stderr="y")

    monkeypatch.setattr(ce.subprocess, "run", _pip_timeout)
    timed = ce._pip_install("python3", ["numpy"], timeout_sec=10)
    assert timed["ok"] is False
    assert timed["error"] == "pip_timeout"

    # _pip_install generic exception.
    monkeypatch.setattr(ce.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("pip broken")))
    pip_err = ce._pip_install("python3", ["numpy"], timeout_sec=10)
    assert pip_err["ok"] is False
    assert "pip broken" in pip_err["error"]

    # _pip_install non-zero exit result.
    monkeypatch.setattr(
        ce.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=2, stdout="", stderr="err"),
    )
    pip_bad = ce._pip_install("python3", ["numpy"], timeout_sec=10)
    assert pip_bad["ok"] is False
    assert pip_bad["exit_code"] == 2


def test_misc_helper_edges_and_path_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # markdown formatting helper image+file branches and empty entries.
    md = ce._format_artifacts_markdown(
        [
            {"name": "main.png", "url": "/charts/x/main.png"},
            {"name": "result.csv", "url": "/charts/x/result.csv"},
            {"name": "", "url": "/x"},
            {"name": "nourl.txt", "url": ""},
        ]
    )
    assert "![main.png]" in md
    assert "下载 result.csv" in md

    # json helpers.
    missing = ce._read_json_dict(tmp_path / "no-file.json")
    assert missing == {}
    p = tmp_path / "bad.json"
    p.write_text("[1,2,3]", encoding="utf-8")
    assert ce._read_json_dict(p) == {}

    # _env_int and policy normalization.
    monkeypatch.setenv("CHART_ENV_TTL_HOURS", "-1")
    monkeypatch.setenv("CHART_ENV_MIN_KEEP", "6")
    monkeypatch.setenv("CHART_ENV_MAX_KEEP", "2")
    policy = ce._chart_env_gc_policy()
    assert policy["min_keep"] == 6
    assert policy["max_keep"] == 6

    # _delete_chart_env_dir invalid path branch.
    assert ce._delete_chart_env_dir({"path": "not-a-path"}) == "invalid_env_path"

    # path traversal guard branches (force helpers to emit unsafe values).
    uploads_dir = tmp_path / "uploads"
    (uploads_dir / "charts").mkdir(parents=True)
    (uploads_dir / "chart_runs").mkdir(parents=True)

    monkeypatch.setattr(ce, "_safe_run_id", lambda _v: "../../etc")
    monkeypatch.setattr(ce, "_safe_any_file_name", lambda _v: "passwd")
    assert ce.resolve_chart_image_path(uploads_dir, "x", "y") is None
    assert ce.resolve_chart_run_meta_path(uploads_dir, "x") is None
