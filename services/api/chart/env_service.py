from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .host import host_call
from .normalize import _clip_text, _iso_now, _normalize_bool

_log = logging.getLogger(__name__)


_CHART_ENV_META_FILE = ".env_meta.json"
_CHART_ENV_GC_STATE_FILE = ".gc_state.json"
_CHART_ENV_LEASE_PREFIX = ".lease_"
_MAX_PIP_TIMEOUT_SEC = 1200


def _venv_scope(packages: List[str]) -> str:
    if not packages:
        return "auto_default"
    canonical = ",".join(sorted({p.lower() for p in packages}))
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]
    return f"pkg_{digest}"


def _env_root(uploads_dir: Path, scope: str) -> Path:
    return uploads_dir / "chart_envs" / scope


def _chart_envs_root(uploads_dir: Path) -> Path:
    return uploads_dir / "chart_envs"


def _env_meta_path(env_dir: Path) -> Path:
    return env_dir / _CHART_ENV_META_FILE


def _env_gc_state_path(envs_root: Path) -> Path:
    return envs_root / _CHART_ENV_GC_STATE_FILE


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # policy: allowed-broad-except
        _log.warning("failed to parse JSON from %s", path, exc_info=True)
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_dict(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = str(os.getenv(name, str(default)) or str(default)).strip()
    try:
        value = int(raw)
    except Exception:  # policy: allowed-broad-except
        _log.debug("non-numeric env var %s=%r, using default %d", name, raw, default)
        value = int(default)
    if value < minimum:
        return int(minimum)
    if value > maximum:
        return int(maximum)
    return int(value)


def _chart_env_gc_policy() -> Dict[str, Any]:
    ttl_hours = _env_int("CHART_ENV_TTL_HOURS", default=72, minimum=1, maximum=24 * 365)
    min_keep = _env_int("CHART_ENV_MIN_KEEP", default=2, minimum=0, maximum=200)
    max_keep = _env_int("CHART_ENV_MAX_KEEP", default=8, minimum=1, maximum=500)
    if max_keep < min_keep:
        max_keep = min_keep
    max_total_mb = _env_int("CHART_ENV_MAX_TOTAL_MB", default=2048, minimum=64, maximum=1024 * 1024)
    return {
        "enabled": _normalize_bool(os.getenv("CHART_ENV_GC_ENABLED"), default=True),
        "interval_sec": _env_int("CHART_ENV_GC_INTERVAL_SEC", default=900, minimum=0, maximum=24 * 3600),
        "ttl_sec": int(ttl_hours * 3600),
        "min_keep": int(min_keep),
        "max_keep": int(max_keep),
        "max_total_bytes": int(max_total_mb * 1024 * 1024),
        "active_grace_sec": _env_int("CHART_ENV_ACTIVE_GRACE_SEC", default=600, minimum=0, maximum=24 * 3600),
        "lease_ttl_sec": _env_int("CHART_ENV_LEASE_TTL_SEC", default=6 * 3600, minimum=60, maximum=7 * 24 * 3600),
    }


def _scope_from_env_dir(env_dir: Path) -> str:
    return str(env_dir.name or "").strip()


def _numeric_ts(value: Any) -> Optional[float]:
    try:
        ts = float(value)
    except Exception:  # policy: allowed-broad-except
        _log.debug("non-numeric timestamp value %r", value)
        return None
    if ts <= 0:
        return None
    return ts


def _env_last_used_ts(env_dir: Path, meta: Dict[str, Any]) -> float:
    meta_ts = _numeric_ts(meta.get("last_used_ts"))
    if meta_ts is not None:
        return meta_ts
    try:
        return float(env_dir.stat().st_mtime)
    except Exception:  # policy: allowed-broad-except
        _log.debug("cannot stat env dir %s for last_used_ts", env_dir)
        return 0.0


def _mark_chart_env_used(env_dir: Path, *, scope: str, packages: List[str], now_ts: Optional[float] = None) -> None:
    ts = float(now_ts if now_ts is not None else time.time())
    env_dir.mkdir(parents=True, exist_ok=True)
    meta_path = _env_meta_path(env_dir)
    current = _read_json_dict(meta_path)
    created_ts = _numeric_ts(current.get("created_ts")) or ts
    payload = {
        "scope": str(scope or _scope_from_env_dir(env_dir)),
        "packages": list(packages),
        "created_ts": float(created_ts),
        "last_used_ts": float(ts),
        "updated_at": datetime.fromtimestamp(ts).isoformat(timespec="seconds"),
    }
    _write_json_dict(meta_path, payload)
    try:
        os.utime(env_dir, (ts, ts))
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to update mtime on env dir %s", env_dir)
        pass  # policy: allowed-broad-except


def _env_lease_path(env_dir: Path, run_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(run_id or "").strip()) or "run"
    return env_dir / f"{_CHART_ENV_LEASE_PREFIX}{safe}"


def _acquire_chart_env_lease(env_dir: Path, run_id: str) -> Path:
    path = _env_lease_path(env_dir, run_id)
    path.write_text(_iso_now(), encoding="utf-8")
    return path


def _release_chart_env_lease(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to release chart env lease %s", path)
        pass  # policy: allowed-broad-except


def _cleanup_stale_chart_env_leases(env_dir: Path, *, now_ts: float, lease_ttl_sec: int) -> None:
    for lease in env_dir.glob(f"{_CHART_ENV_LEASE_PREFIX}*"):
        try:
            mtime = float(lease.stat().st_mtime)
        except Exception:  # policy: allowed-broad-except
            _log.debug("cannot stat lease file %s", lease)
            continue
        if (now_ts - mtime) > float(max(1, lease_ttl_sec)):
            try:
                lease.unlink(missing_ok=True)
            except Exception:  # policy: allowed-broad-except
                _log.debug("failed to remove stale lease %s", lease)
                pass  # policy: allowed-broad-except


def _has_active_chart_env_lease(env_dir: Path) -> bool:
    try:
        return any(env_dir.glob(f"{_CHART_ENV_LEASE_PREFIX}*"))
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to check active leases in %s", env_dir)
        return False


def _dir_size_bytes(path: Path) -> int:
    total = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += int(entry.stat(follow_symlinks=False).st_size)
                    except Exception:  # policy: allowed-broad-except
                        _log.debug("cannot stat entry in %s", cur)
                        continue
        except Exception:  # policy: allowed-broad-except
            _log.debug("cannot scan directory %s", cur)
            continue
    return int(total)


def _delete_chart_env_dir(item: Dict[str, Any]) -> Optional[str]:
    target = item.get("path")
    if not isinstance(target, Path):
        return "invalid_env_path"
    try:
        shutil.rmtree(target)
    except Exception as exc:  # policy: allowed-broad-except
        _log.debug("file cleanup failed", exc_info=True)
        return str(exc)
    return None


def _prune_disabled_report(envs_root: Path) -> Dict[str, Any]:
    return {
        "enabled": False,
        "skipped": "disabled",
        "root": str(envs_root),
        "before_count": 0,
        "after_count": 0,
        "before_size_bytes": 0,
        "after_size_bytes": 0,
        "reclaimed_bytes": 0,
        "deleted_scopes": [],
        "failed": [],
    }


def _normalize_prune_limits(pol: Dict[str, Any]) -> Dict[str, int]:
    min_keep = max(0, int(pol.get("min_keep") or 0))
    max_keep = max(min_keep, int(pol.get("max_keep") or 0))
    return {
        "min_keep": min_keep,
        "max_keep": max_keep,
        "ttl_sec": max(0, int(pol.get("ttl_sec") or 0)),
        "max_total_bytes": max(0, int(pol.get("max_total_bytes") or 0)),
        "active_grace_sec": max(0, int(pol.get("active_grace_sec") or 0)),
        "lease_ttl_sec": max(60, int(pol.get("lease_ttl_sec") or 3600)),
    }


def _collect_prune_items(
    envs_root: Path,
    *,
    keep_scopes: set[str],
    now_ts: float,
    lease_ttl_sec: int,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for child in sorted(envs_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        scope = _scope_from_env_dir(child)
        if not scope or scope.startswith("."):
            continue
        _cleanup_stale_chart_env_leases(child, now_ts=now_ts, lease_ttl_sec=lease_ttl_sec)
        meta = _read_json_dict(_env_meta_path(child))
        last_used_ts = _env_last_used_ts(child, meta)
        size_bytes = _dir_size_bytes(child)
        items.append(
            {
                "scope": scope,
                "path": child,
                "size_bytes": int(size_bytes),
                "last_used_ts": float(last_used_ts),
                "age_sec": max(0, int(now_ts - last_used_ts)),
                "keep_scope": bool(scope in keep_scopes),
                "active_lease": _has_active_chart_env_lease(child),
            }
        )
    return items


def _is_prune_item_eligible(item: Dict[str, Any], *, active_grace_sec: int) -> bool:
    if item.get("keep_scope"):
        return False
    if item.get("active_lease"):
        return False
    if int(item.get("age_sec") or 0) < active_grace_sec:
        return False
    return True


def _oldest_eligible_prune_item(
    remaining: List[Dict[str, Any]], *, active_grace_sec: int
) -> Optional[Dict[str, Any]]:
    candidates = [
        item
        for item in remaining
        if _is_prune_item_eligible(item, active_grace_sec=active_grace_sec)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: float(item.get("last_used_ts") or 0))
    return candidates[0]


def _remove_prune_item(
    remaining: List[Dict[str, Any]],
    *,
    target: Dict[str, Any],
    reason: str,
    deleted_scopes: List[str],
    failed: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    err = host_call("_delete_chart_env_dir", target)
    if err:
        failed.append({"scope": target.get("scope"), "reason": reason, "error": err})
        return remaining
    scope = str(target.get("scope") or "")
    deleted_scopes.append(scope)
    return [item for item in remaining if str(item.get("scope") or "") != scope]


def _prune_by_ttl(
    remaining: List[Dict[str, Any]],
    *,
    ttl_sec: int,
    min_keep: int,
    active_grace_sec: int,
    deleted_scopes: List[str],
    failed: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if ttl_sec <= 0:
        return remaining
    for item in sorted(remaining, key=lambda x: float(x.get("last_used_ts") or 0)):
        if len(remaining) <= min_keep:
            break
        if not _is_prune_item_eligible(item, active_grace_sec=active_grace_sec):
            continue
        if int(item.get("age_sec") or 0) < ttl_sec:
            continue
        remaining = _remove_prune_item(
            remaining,
            target=item,
            reason="ttl",
            deleted_scopes=deleted_scopes,
            failed=failed,
        )
    return remaining


def _prune_by_max_keep(
    remaining: List[Dict[str, Any]],
    *,
    max_keep: int,
    min_keep: int,
    active_grace_sec: int,
    deleted_scopes: List[str],
    failed: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    while len(remaining) > max_keep:
        if len(remaining) <= min_keep:
            break
        victim = _oldest_eligible_prune_item(
            remaining, active_grace_sec=active_grace_sec
        )
        if victim is None:
            break
        remaining = _remove_prune_item(
            remaining,
            target=victim,
            reason="max_keep",
            deleted_scopes=deleted_scopes,
            failed=failed,
        )
    return remaining


def _prune_by_max_total_bytes(
    remaining: List[Dict[str, Any]],
    *,
    max_total_bytes: int,
    min_keep: int,
    active_grace_sec: int,
    deleted_scopes: List[str],
    failed: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if max_total_bytes <= 0:
        return remaining
    while True:
        total_bytes = int(sum(int(item.get("size_bytes") or 0) for item in remaining))
        if total_bytes <= max_total_bytes or len(remaining) <= min_keep:
            break
        victim = _oldest_eligible_prune_item(
            remaining, active_grace_sec=active_grace_sec
        )
        if victim is None:
            break
        remaining = _remove_prune_item(
            remaining,
            target=victim,
            reason="max_total_bytes",
            deleted_scopes=deleted_scopes,
            failed=failed,
        )
    return remaining


def _prune_chart_envs(
    uploads_dir: Path,
    *,
    keep_scopes: set[str],
    policy: Optional[Dict[str, Any]] = None,
    now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    pol = dict(policy or _chart_env_gc_policy())
    envs_root = _chart_envs_root(uploads_dir)
    envs_root.mkdir(parents=True, exist_ok=True)
    ts_now = float(now_ts if now_ts is not None else time.time())
    if not _normalize_bool(pol.get("enabled"), default=True):
        return _prune_disabled_report(envs_root)

    limits = _normalize_prune_limits(pol)
    items = _collect_prune_items(
        envs_root,
        keep_scopes=keep_scopes,
        now_ts=ts_now,
        lease_ttl_sec=limits["lease_ttl_sec"],
    )

    before_count = len(items)
    before_size_bytes = int(sum(int(item.get("size_bytes") or 0) for item in items))
    deleted_scopes: List[str] = []
    failed: List[Dict[str, Any]] = []

    remaining: List[Dict[str, Any]] = list(items)
    remaining = _prune_by_ttl(
        remaining,
        ttl_sec=limits["ttl_sec"],
        min_keep=limits["min_keep"],
        active_grace_sec=limits["active_grace_sec"],
        deleted_scopes=deleted_scopes,
        failed=failed,
    )
    remaining = _prune_by_max_keep(
        remaining,
        max_keep=limits["max_keep"],
        min_keep=limits["min_keep"],
        active_grace_sec=limits["active_grace_sec"],
        deleted_scopes=deleted_scopes,
        failed=failed,
    )
    remaining = _prune_by_max_total_bytes(
        remaining,
        max_total_bytes=limits["max_total_bytes"],
        min_keep=limits["min_keep"],
        active_grace_sec=limits["active_grace_sec"],
        deleted_scopes=deleted_scopes,
        failed=failed,
    )

    after_count = len(remaining)
    after_size_bytes = int(sum(int(item.get("size_bytes") or 0) for item in remaining))
    return {
        "enabled": True,
        "root": str(envs_root),
        "before_count": before_count,
        "after_count": after_count,
        "before_size_bytes": before_size_bytes,
        "after_size_bytes": after_size_bytes,
        "reclaimed_bytes": max(0, before_size_bytes - after_size_bytes),
        "deleted_scopes": deleted_scopes,
        "failed": failed,
    }


def _maybe_prune_chart_envs(uploads_dir: Path, *, keep_scopes: set[str], policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    pol = dict(policy or _chart_env_gc_policy())
    envs_root = _chart_envs_root(uploads_dir)
    envs_root.mkdir(parents=True, exist_ok=True)
    if not _normalize_bool(pol.get("enabled"), default=True):
        return {
            "enabled": False,
            "skipped": "disabled",
            "root": str(envs_root),
        }
    interval_sec = max(0, int(pol.get("interval_sec") or 0))
    now_ts = float(time.time())
    state_path = _env_gc_state_path(envs_root)
    state = _read_json_dict(state_path)
    last_gc_ts = _numeric_ts(state.get("last_gc_ts")) or 0.0
    if interval_sec > 0 and last_gc_ts > 0 and (now_ts - last_gc_ts) < interval_sec:
        return {
            "enabled": True,
            "skipped": "interval",
            "interval_sec": interval_sec,
            "last_gc_ts": last_gc_ts,
            "next_gc_ts": last_gc_ts + interval_sec,
            "root": str(envs_root),
        }
    report = host_call("_prune_chart_envs", uploads_dir, keep_scopes=keep_scopes, policy=pol, now_ts=now_ts)
    try:
        host_call(
            "_write_json_dict",
            state_path,
            {
                "last_gc_ts": now_ts,
                "last_gc_at": datetime.fromtimestamp(now_ts).isoformat(timespec="seconds"),
                "last_gc_report": report,
            },
        )
    except Exception:  # policy: allowed-broad-except
        _log.warning("failed to write GC state to %s", state_path, exc_info=True)
        pass  # policy: allowed-broad-except
    report["interval_sec"] = interval_sec
    report["last_gc_ts"] = now_ts
    return report


def _env_python_path(env_dir: Path) -> Path:
    unix = env_dir / "bin" / "python"
    if unix.exists():
        return unix
    return env_dir / "Scripts" / "python.exe"


def _ensure_venv(env_dir: Path) -> Dict[str, Any]:
    env_dir.mkdir(parents=True, exist_ok=True)
    py_path = _env_python_path(env_dir)
    if py_path.exists():
        return {"ok": True, "python": str(py_path)}
    try:
        proc = subprocess.run(
            ["python3", "-m", "venv", str(env_dir)],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as exc:  # policy: allowed-broad-except
        _log.debug("operation failed", exc_info=True)
        return {"ok": False, "error": str(exc)}
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": "venv_create_failed",
            "stdout": _clip_text(proc.stdout or ""),
            "stderr": _clip_text(proc.stderr or ""),
        }
    py_path = _env_python_path(env_dir)
    if not py_path.exists():
        return {"ok": False, "error": "venv_python_missing"}
    return {"ok": True, "python": str(py_path)}


def _pip_install(python_exec: str, packages: List[str], timeout_sec: int) -> Dict[str, Any]:
    if not packages:
        return {"ok": True, "packages": []}
    cmd = [python_exec, "-m", "pip", "install", *packages]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(30, min(timeout_sec, _MAX_PIP_TIMEOUT_SEC)),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return {
            "ok": False,
            "error": "pip_timeout",
            "packages": packages,
            "stdout": _clip_text(stdout),
            "stderr": _clip_text((stderr + "\npip install timed out").strip()),
        }
    except Exception as exc:  # policy: allowed-broad-except
        _log.debug("operation failed", exc_info=True)
        return {"ok": False, "error": str(exc), "packages": packages}
    return {
        "ok": proc.returncode == 0,
        "packages": packages,
        "exit_code": int(proc.returncode),
        "stdout": _clip_text(proc.stdout or ""),
        "stderr": _clip_text(proc.stderr or ""),
    }

