from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_DEFAULT_TIMEOUT_SEC = 120
_MAX_TIMEOUT_SEC = 3600
_DEFAULT_EXEC_RETRIES = 1
_MAX_EXEC_RETRIES = 6
_MAX_STD_CHARS = 60000
_MAX_PACKAGES = 24
_MAX_PIP_TIMEOUT_SEC = 1200
_CHART_ENV_META_FILE = ".env_meta.json"
_CHART_ENV_GC_STATE_FILE = ".gc_state.json"
_CHART_ENV_LEASE_PREFIX = ".lease_"


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_run_id(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return text if _RUN_ID_RE.fullmatch(text) else None


def _safe_file_name(value: Any, default: str = "main.png") -> str:
    raw = str(value or "").strip()
    if not raw:
        return default
    name = Path(raw).name
    if not _FILE_RE.fullmatch(name):
        return default
    if not name.lower().endswith(".png"):
        name = f"{name}.png"
    return name


def _safe_any_file_name(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    name = Path(raw).name
    if not _FILE_RE.fullmatch(name):
        return None
    return name


_PREVIEWABLE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}


def _format_artifacts_markdown(artifacts: List[Dict[str, Any]]) -> str:
    """Generate markdown for artifacts: inline preview for images, download link for others."""
    lines: List[str] = []
    for art in artifacts:
        name = str(art.get("name") or "")
        url = str(art.get("url") or "")
        if not name or not url:
            continue
        ext = Path(name).suffix.lower()
        if ext in _PREVIEWABLE_EXTS:
            lines.append(f"![{name}]({url})")
            lines.append(f"[下载 {name}]({url})")
        else:
            lines.append(f"[下载 {name}]({url})")
    return "\n\n".join(lines)


def _clip_text(value: str) -> str:
    if len(value) <= _MAX_STD_CHARS:
        return value
    return value[:_MAX_STD_CHARS] + "\n...[truncated]..."


def _normalize_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except Exception:
        _log.debug("non-numeric timeout value %r, using default", value)
        return _DEFAULT_TIMEOUT_SEC
    if timeout <= 0:
        return _DEFAULT_TIMEOUT_SEC
    return min(timeout, _MAX_TIMEOUT_SEC)


def _normalize_retries(value: Any) -> int:
    try:
        retries = int(value)
    except Exception:
        _log.debug("non-numeric retries value %r, using default", value)
        return _DEFAULT_EXEC_RETRIES
    if retries <= 0:
        return _DEFAULT_EXEC_RETRIES
    return min(retries, _MAX_EXEC_RETRIES)


def _normalize_bool(value: Any, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _normalize_packages(value: Any) -> List[str]:
    raw: List[str] = []
    if isinstance(value, list):
        raw = [str(x or "").strip() for x in value]
    elif isinstance(value, str):
        raw = [x.strip() for x in re.split(r"[,\s;；，]+", value) if x.strip()]
    out: List[str] = []
    for item in raw:
        pkg = item.strip()
        if not pkg:
            continue
        if not _PACKAGE_RE.fullmatch(pkg):
            continue
        key = pkg.lower()
        if key not in {x.lower() for x in out}:
            out.append(pkg)
        if len(out) >= _MAX_PACKAGES:
            break
    return out


def _extract_missing_module(stderr: str) -> Optional[str]:
    if not stderr:
        return None
    patterns = [
        r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]",
        r"ImportError:\s+No module named\s+([A-Za-z0-9_.-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, stderr)
        if not match:
            continue
        value = str(match.group(1) or "").strip().split(".")[0]
        if _PACKAGE_RE.fullmatch(value):
            return value
    return None


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
    except Exception:
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
    except Exception:
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
    except Exception:
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
    except Exception:
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
    except Exception:
        _log.debug("failed to update mtime on env dir %s", env_dir)
        pass


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
    except Exception:
        _log.debug("failed to release chart env lease %s", path)
        pass


def _cleanup_stale_chart_env_leases(env_dir: Path, *, now_ts: float, lease_ttl_sec: int) -> None:
    for lease in env_dir.glob(f"{_CHART_ENV_LEASE_PREFIX}*"):
        try:
            mtime = float(lease.stat().st_mtime)
        except Exception:
            _log.debug("cannot stat lease file %s", lease)
            continue
        if (now_ts - mtime) > float(max(1, lease_ttl_sec)):
            try:
                lease.unlink(missing_ok=True)
            except Exception:
                _log.debug("failed to remove stale lease %s", lease)
                pass


def _has_active_chart_env_lease(env_dir: Path) -> bool:
    try:
        return any(env_dir.glob(f"{_CHART_ENV_LEASE_PREFIX}*"))
    except Exception:
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
                    except Exception:
                        _log.debug("cannot stat entry in %s", cur)
                        continue
        except Exception:
            _log.debug("cannot scan directory %s", cur)
            continue
    return int(total)


def _delete_chart_env_dir(item: Dict[str, Any]) -> Optional[str]:
    target = item.get("path")
    if not isinstance(target, Path):
        return "invalid_env_path"
    try:
        shutil.rmtree(target)
    except Exception as exc:
        _log.debug("file cleanup failed", exc_info=True)
        return str(exc)
    return None


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

    min_keep = max(0, int(pol.get("min_keep") or 0))
    max_keep = max(min_keep, int(pol.get("max_keep") or 0))
    ttl_sec = max(0, int(pol.get("ttl_sec") or 0))
    max_total_bytes = max(0, int(pol.get("max_total_bytes") or 0))
    active_grace_sec = max(0, int(pol.get("active_grace_sec") or 0))
    lease_ttl_sec = max(60, int(pol.get("lease_ttl_sec") or 3600))

    items: List[Dict[str, Any]] = []
    for child in sorted(envs_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        scope = _scope_from_env_dir(child)
        if not scope or scope.startswith("."):
            continue
        _cleanup_stale_chart_env_leases(child, now_ts=ts_now, lease_ttl_sec=lease_ttl_sec)
        meta = _read_json_dict(_env_meta_path(child))
        last_used_ts = _env_last_used_ts(child, meta)
        size_bytes = _dir_size_bytes(child)
        age_sec = max(0, int(ts_now - last_used_ts))
        items.append(
            {
                "scope": scope,
                "path": child,
                "size_bytes": int(size_bytes),
                "last_used_ts": float(last_used_ts),
                "age_sec": age_sec,
                "keep_scope": bool(scope in keep_scopes),
                "active_lease": _has_active_chart_env_lease(child),
            }
        )

    before_count = len(items)
    before_size_bytes = int(sum(int(item.get("size_bytes") or 0) for item in items))
    deleted_scopes: List[str] = []
    failed: List[Dict[str, Any]] = []

    remaining: List[Dict[str, Any]] = list(items)

    def _is_eligible(item: Dict[str, Any]) -> bool:
        if item.get("keep_scope"):
            return False
        if item.get("active_lease"):
            return False
        if int(item.get("age_sec") or 0) < active_grace_sec:
            return False
        return True

    def _oldest_eligible() -> Optional[Dict[str, Any]]:
        candidates = [item for item in remaining if _is_eligible(item)]
        if not candidates:
            return None
        candidates.sort(key=lambda item: float(item.get("last_used_ts") or 0))
        return candidates[0]

    def _remove_item(target: Dict[str, Any], reason: str) -> bool:
        nonlocal remaining
        err = _delete_chart_env_dir(target)
        if err:
            failed.append({"scope": target.get("scope"), "reason": reason, "error": err})
            return False
        deleted_scopes.append(str(target.get("scope") or ""))
        remaining = [item for item in remaining if str(item.get("scope") or "") != str(target.get("scope") or "")]
        return True

    if ttl_sec > 0:
        for item in sorted(remaining, key=lambda x: float(x.get("last_used_ts") or 0)):
            if len(remaining) <= min_keep:
                break
            if not _is_eligible(item):
                continue
            if int(item.get("age_sec") or 0) < ttl_sec:
                continue
            _remove_item(item, reason="ttl")

    while len(remaining) > max_keep:
        if len(remaining) <= min_keep:
            break
        victim = _oldest_eligible()
        if victim is None:
            break
        _remove_item(victim, reason="max_keep")

    while max_total_bytes > 0:
        total_bytes = int(sum(int(item.get("size_bytes") or 0) for item in remaining))
        if total_bytes <= max_total_bytes or len(remaining) <= min_keep:
            break
        victim = _oldest_eligible()
        if victim is None:
            break
        _remove_item(victim, reason="max_total_bytes")

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
    report = _prune_chart_envs(uploads_dir, keep_scopes=keep_scopes, policy=pol, now_ts=now_ts)
    try:
        _write_json_dict(
            state_path,
            {
                "last_gc_ts": now_ts,
                "last_gc_at": datetime.fromtimestamp(now_ts).isoformat(timespec="seconds"),
                "last_gc_report": report,
            },
        )
    except Exception:
        _log.warning("failed to write GC state to %s", state_path, exc_info=True)
        pass
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
    except Exception as exc:
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
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        return {"ok": False, "error": str(exc), "packages": packages}
    return {
        "ok": proc.returncode == 0,
        "packages": packages,
        "exit_code": int(proc.returncode),
        "stdout": _clip_text(proc.stdout or ""),
        "stderr": _clip_text(proc.stderr or ""),
    }


def _build_runner_source(
    python_code: str,
    input_payload: Any,
    output_dir: Path,
    main_image: Path,
    filesystem_guard: str = "",
) -> str:
    input_json = json.dumps(input_payload, ensure_ascii=False)
    input_json_text = json.dumps(input_json, ensure_ascii=False)
    output_dir_json = json.dumps(str(output_dir))
    main_image_json = json.dumps(str(main_image))
    code_json = json.dumps(python_code, ensure_ascii=False)
    guard_prefix = filesystem_guard + "\n" if filesystem_guard else ""
    return (
        guard_prefix +
        "import json\n"
        "import os\n"
        "import traceback\n"
        "os.environ.setdefault('MPLBACKEND', 'Agg')\n"
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        "try:\n"
        "    import numpy as np\n"
        "except Exception:\n"
        "    np = None\n"
        "try:\n"
        "    import pandas as pd\n"
        "except Exception:\n"
        "    pd = None\n"
        "try:\n"
        "    import seaborn as sns\n"
        "except Exception:\n"
        "    sns = None\n"
        f"PAYLOAD_JSON = {input_json_text}\n"
        "INPUT_DATA = json.loads(PAYLOAD_JSON)\n"
        f"OUTPUT_DIR = {output_dir_json}\n"
        f"MAIN_IMAGE = {main_image_json}\n"
        "ARTIFACTS = []\n"
        "os.makedirs(OUTPUT_DIR, exist_ok=True)\n"
        "def save_chart(name=None, dpi=160, bbox_inches='tight'):\n"
        "    target = MAIN_IMAGE if not name else os.path.join(OUTPUT_DIR, os.path.basename(str(name)))\n"
        "    if not str(target).lower().endswith('.png'):\n"
        "        target = target + '.png'\n"
        "    plt.savefig(target, dpi=dpi, bbox_inches=bbox_inches)\n"
        "    if target not in ARTIFACTS:\n"
        "        ARTIFACTS.append(target)\n"
        "    return target\n"
        "def save_text(name, content):\n"
        "    target = os.path.join(OUTPUT_DIR, os.path.basename(str(name)))\n"
        "    with open(target, 'w', encoding='utf-8') as f:\n"
        "        f.write(str(content))\n"
        "    if target not in ARTIFACTS:\n"
        "        ARTIFACTS.append(target)\n"
        "    return target\n"
        "def save_file(src_or_name, content=None):\n"
        "    import shutil as _shutil\n"
        "    if content is not None:\n"
        "        target = os.path.join(OUTPUT_DIR, os.path.basename(str(src_or_name)))\n"
        "        mode = 'wb' if isinstance(content, (bytes, bytearray)) else 'w'\n"
        "        with open(target, mode) as f:\n"
        "            f.write(content)\n"
        "    elif os.path.isfile(src_or_name):\n"
        "        target = os.path.join(OUTPUT_DIR, os.path.basename(str(src_or_name)))\n"
        "        _shutil.copy2(src_or_name, target)\n"
        "    else:\n"
        "        return None\n"
        "    if target not in ARTIFACTS:\n"
        "        ARTIFACTS.append(target)\n"
        "    return target\n"
        "ENV = {\n"
        "    'input_data': INPUT_DATA,\n"
        "    'plt': plt,\n"
        "    'np': np,\n"
        "    'pd': pd,\n"
        "    'sns': sns,\n"
        "    'save_chart': save_chart,\n"
        "    'save_text': save_text,\n"
        "    'save_file': save_file,\n"
        "    'OUTPUT_DIR': OUTPUT_DIR,\n"
        "    'MAIN_IMAGE': MAIN_IMAGE,\n"
        "}\n"
        f"USER_CODE = {code_json}\n"
        "try:\n"
        "    exec(compile(USER_CODE, '<chart.exec>', 'exec'), ENV, ENV)\n"
        "    if not os.path.exists(MAIN_IMAGE) and plt.get_fignums():\n"
        "        save_chart()\n"
        "except Exception:\n"
        "    traceback.print_exc()\n"
        "    raise\n"
        "finally:\n"
        "    plt.close('all')\n"
        "print('CHART_MAIN=' + (MAIN_IMAGE if os.path.exists(MAIN_IMAGE) else ''))\n"
        "print('CHART_ARTIFACTS=' + json.dumps(ARTIFACTS, ensure_ascii=False))\n"
    )


def execute_chart_exec(args: Dict[str, Any], app_root: Path, uploads_dir: Path) -> Dict[str, Any]:
    from .chart_sandbox import (
        build_filesystem_guard_source,
        build_sanitized_env,
        make_preexec_fn,
        scan_code_patterns,
    )
    from .global_limits import GLOBAL_CHART_EXEC_SEMAPHORE

    python_code = str(args.get("python_code") or "")
    if not python_code.strip():
        return {"error": "missing_python_code"}

    execution_profile = str(args.get("execution_profile") or "trusted").strip()
    if execution_profile not in ("template", "trusted", "sandboxed"):
        execution_profile = "trusted"

    # Sandboxed profile: scan code before execution
    if execution_profile == "sandboxed":
        scan_result = scan_code_patterns(python_code, execution_profile)
        if scan_result is not None:
            return scan_result

    # Concurrency control
    acquired = GLOBAL_CHART_EXEC_SEMAPHORE.acquire(timeout=30)
    if not acquired:
        return {"error": "chart_exec_busy", "message": "Too many concurrent chart executions"}

    try:
        return _execute_chart_exec_inner(
            args, app_root, uploads_dir, python_code, execution_profile,
        )
    finally:
        GLOBAL_CHART_EXEC_SEMAPHORE.release()


def _execute_chart_exec_inner(
    args: Dict[str, Any],
    app_root: Path,
    uploads_dir: Path,
    python_code: str,
    execution_profile: str,
) -> Dict[str, Any]:
    from .chart_sandbox import (
        build_filesystem_guard_source,
        build_sanitized_env,
        make_preexec_fn,
    )

    run_id = f"chr_{uuid.uuid4().hex[:12]}"
    timeout_sec = _normalize_timeout(args.get("timeout_sec"))
    exec_retries = _normalize_retries(args.get("max_retries"))
    auto_install = _normalize_bool(args.get("auto_install"), default=False)
    requested_packages = _normalize_packages(args.get("packages"))
    save_as = _safe_file_name(args.get("save_as"), default="main.png")
    chart_hint = str(args.get("chart_hint") or "").strip()
    input_data = args.get("input_data")

    chart_root = uploads_dir / "charts"
    run_root = uploads_dir / "chart_runs"
    output_dir = chart_root / run_id
    run_dir = run_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    main_image = output_dir / save_as
    script_path = run_dir / "run.py"
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    meta_path = run_dir / "meta.json"

    # Build filesystem guard for sandboxed profile
    fs_guard = ""
    if execution_profile == "sandboxed":
        data_dir = str(uploads_dir.parent / "data")
        fs_guard = build_filesystem_guard_source(
            str(output_dir), [str(output_dir), str(uploads_dir), data_dir]
        )

    script_source = _build_runner_source(
        python_code, input_data, output_dir, main_image, filesystem_guard=fs_guard
    )
    script_path.write_text(script_source, encoding="utf-8")
    try:
        (run_dir / "input.json").write_text(json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        _log.debug("failed to serialize input_data for run %s, writing null", run_id)
        (run_dir / "input.json").write_text("null\n", encoding="utf-8")

    started_at = _iso_now()
    python_exec = "python3"
    env_scope: Optional[str] = None
    env_dir: Optional[Path] = None
    lease_path: Optional[Path] = None
    installed_packages: List[str] = []
    install_logs: List[Dict[str, Any]] = []
    attempts: List[Dict[str, Any]] = []
    env_gc: Dict[str, Any] = {"enabled": False, "skipped": "auto_install_disabled"}
    timed_out = False
    exit_code = -1
    stdout = ""
    stderr = ""
    try:
        if auto_install:
            env_scope = _venv_scope(requested_packages)
            try:
                env_gc = _maybe_prune_chart_envs(uploads_dir, keep_scopes={env_scope})
            except Exception as exc:
                _log.debug("operation failed", exc_info=True)
                env_gc = {"enabled": True, "error": "gc_failed", "detail": str(exc)}
            env_dir = _env_root(uploads_dir, env_scope)
            venv_result = _ensure_venv(env_dir)
            if not venv_result.get("ok"):
                error_payload = {
                    "error": "venv_init_failed",
                    "run_id": run_id,
                    "detail": venv_result,
                    "environment_scope": env_scope,
                    "env_gc": env_gc,
                    "meta_url": f"/chart-runs/{run_id}/meta",
                }
                meta_path.write_text(
                    json.dumps({"run_id": run_id, "ok": False, **error_payload}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return error_payload
            python_exec = str(venv_result.get("python") or _env_python_path(env_dir))
            try:
                _mark_chart_env_used(env_dir, scope=env_scope, packages=requested_packages)
            except Exception:
                _log.debug("failed to mark chart env used for scope %s", env_scope)
                pass
            try:
                lease_path = _acquire_chart_env_lease(env_dir, run_id)
            except Exception:
                _log.warning("failed to acquire chart env lease for run %s", run_id, exc_info=True)
                lease_path = None
            if requested_packages:
                pre_install = _pip_install(python_exec, requested_packages, timeout_sec=max(120, timeout_sec * 4))
                install_logs.append({"phase": "requested_packages", **pre_install})
                if pre_install.get("ok"):
                    installed_packages.extend(requested_packages)

        # Snapshot cwd files before execution to detect new outputs
        _cwd_before: set[str] = set()
        try:
            _cwd_before = {e.name for e in os.scandir(str(app_root)) if e.is_file(follow_symlinks=False)}
        except Exception:
            _log.debug("failed to snapshot cwd before execution")

        auto_installed_missing: set[str] = set()
        sandbox_env = build_sanitized_env(execution_profile)
        sandbox_preexec = make_preexec_fn(execution_profile, timeout_sec)
        for attempt in range(1, exec_retries + 1):
            cur_timed_out = False
            cur_exit_code = -1
            cur_stdout = ""
            cur_stderr = ""
            try:
                proc = subprocess.run(
                    [python_exec, str(script_path)],
                    cwd=str(app_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    env=sandbox_env,
                    preexec_fn=sandbox_preexec,
                )
                cur_exit_code = int(proc.returncode)
                cur_stdout = proc.stdout or ""
                cur_stderr = proc.stderr or ""
            except subprocess.TimeoutExpired as exc:
                cur_timed_out = True
                cur_exit_code = -1
                cur_stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
                cur_stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
                cur_stderr = (cur_stderr + "\nprocess timed out").strip()
            except Exception as exc:
                _log.debug("operation failed", exc_info=True)
                cur_exit_code = -1
                cur_stderr = str(exc)

            cur_stdout = _clip_text(cur_stdout)
            cur_stderr = _clip_text(cur_stderr)
            attempts.append(
                {
                    "attempt": attempt,
                    "exit_code": cur_exit_code,
                    "timed_out": cur_timed_out,
                    "stdout": cur_stdout,
                    "stderr": cur_stderr,
                }
            )
            exit_code = cur_exit_code
            timed_out = cur_timed_out
            stdout = cur_stdout
            stderr = cur_stderr
            if cur_exit_code == 0:
                break

            missing_module = _extract_missing_module(cur_stderr)
            if (
                auto_install
                and (attempt < exec_retries)
                and missing_module
                and (missing_module not in auto_installed_missing)
            ):
                auto_installed_missing.add(missing_module)
                install_res = _pip_install(python_exec, [missing_module], timeout_sec=max(120, timeout_sec * 3))
                install_logs.append({"phase": f"missing_module_attempt_{attempt}", **install_res})
                if install_res.get("ok"):
                    if missing_module.lower() not in {p.lower() for p in installed_packages}:
                        installed_packages.append(missing_module)
                    continue
            break
    finally:
        _release_chart_env_lease(lease_path)
        if env_dir is not None:
            try:
                _mark_chart_env_used(
                    env_dir,
                    scope=env_scope or _scope_from_env_dir(env_dir),
                    packages=requested_packages,
                )
            except Exception:
                _log.debug("failed to mark chart env used in finally for scope %s", env_scope)
                pass

    # Capture new files from cwd that weren't there before execution
    try:
        _cwd_after = {e.name for e in os.scandir(str(app_root)) if e.is_file(follow_symlinks=False)}
        _new_files = _cwd_after - _cwd_before
        for fname in sorted(_new_files):
            src = Path(app_root) / fname
            dst = output_dir / fname
            if not dst.exists():
                try:
                    shutil.copy2(str(src), str(dst))
                    _log.debug("captured new cwd file %s → %s", fname, dst)
                except Exception:
                    _log.debug("failed to capture cwd file %s", fname)
    except Exception:
        _log.debug("failed to scan cwd for new files after execution")

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    artifacts: List[Dict[str, Any]] = []
    image_url: Optional[str] = None
    if output_dir.exists():
        for path in sorted(output_dir.iterdir(), key=lambda p: p.name):
            if not path.is_file():
                continue
            url = f"/charts/{run_id}/{path.name}"
            artifacts.append({"name": path.name, "url": url, "size": path.stat().st_size})
            if image_url is None and path.name.lower().endswith(".png"):
                image_url = url

    ok = (exit_code == 0) and (bool(image_url) or bool(artifacts))
    artifacts_markdown = _format_artifacts_markdown(artifacts)
    finished_at = _iso_now()

    meta = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "timeout_sec": timeout_sec,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "ok": ok,
        "chart_hint": chart_hint,
        "script": str(script_path),
        "output_dir": str(output_dir),
        "python_executable": python_exec,
        "environment_dir": str(env_dir) if env_dir else None,
        "environment_scope": env_scope,
        "auto_install": auto_install,
        "requested_packages": requested_packages,
        "installed_packages": installed_packages,
        "install_logs": install_logs,
        "env_gc": env_gc,
        "attempts": attempts,
        "stdout_file": str(stdout_path),
        "stderr_file": str(stderr_path),
        "image_url": image_url,
        "artifacts": artifacts,
        "artifacts_markdown": artifacts_markdown,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": ok,
        "run_id": run_id,
        "timed_out": timed_out,
        "timeout_sec": timeout_sec,
        "exit_code": exit_code,
        "image_url": image_url,
        "artifacts": artifacts,
        "artifacts_markdown": artifacts_markdown,
        "stdout": stdout,
        "stderr": stderr,
        "python_executable": python_exec,
        "environment_dir": str(env_dir) if env_dir else None,
        "environment_scope": env_scope,
        "auto_install": auto_install,
        "requested_packages": requested_packages,
        "installed_packages": installed_packages,
        "install_logs": install_logs,
        "env_gc": env_gc,
        "attempts": attempts,
        "meta_url": f"/chart-runs/{run_id}/meta",
    }


def resolve_chart_image_path(uploads_dir: Path, run_id: str, file_name: str) -> Optional[Path]:
    safe_run_id = _safe_run_id(run_id)
    safe_name = _safe_any_file_name(file_name)
    if not safe_run_id or not safe_name:
        return None
    root = (uploads_dir / "charts").resolve()
    path = (root / safe_run_id / safe_name).resolve()
    if root not in path.parents:
        return None
    if not path.exists() or not path.is_file():
        return None
    return path


def resolve_chart_run_meta_path(uploads_dir: Path, run_id: str) -> Optional[Path]:
    safe_run_id = _safe_run_id(run_id)
    if not safe_run_id:
        return None
    root = (uploads_dir / "chart_runs").resolve()
    path = (root / safe_run_id / "meta.json").resolve()
    if root not in path.parents:
        return None
    if not path.exists() or not path.is_file():
        return None
    return path
