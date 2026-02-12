"""Chart execution sandbox: environment sanitization, resource limits, code scanning."""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Execution profiles
# ---------------------------------------------------------------------------
PROFILES = ("template", "trusted", "sandboxed")

# ---------------------------------------------------------------------------
# Environment variable sanitization
# ---------------------------------------------------------------------------
_SENSITIVE_RE = re.compile(
    r"(SECRET|PASSWORD|MASTER_KEY|API_KEY|TOKEN|REDIS_URL|AWS_|OSS_)",
    re.IGNORECASE,
)

_ENV_WHITELIST = {
    "PATH", "HOME", "LANG", "LC_ALL", "PYTHONPATH",
    "MPLBACKEND", "DATA_DIR", "UPLOADS_DIR", "VIRTUAL_ENV",
    "TMPDIR", "TMP", "TEMP",
}


def build_sanitized_env(profile: str = "trusted") -> Dict[str, str]:
    """Return a sanitized copy of os.environ for subprocess execution."""
    if profile not in PROFILES:
        profile = "trusted"

    base = dict(os.environ)

    if profile == "sandboxed":
        return {k: v for k, v in base.items() if k in _ENV_WHITELIST}

    # trusted / template: strip sensitive vars, keep the rest
    return {k: v for k, v in base.items() if not _SENSITIVE_RE.search(k)}


# ---------------------------------------------------------------------------
# Resource limits (preexec_fn for subprocess)
# ---------------------------------------------------------------------------

_RESOURCE_LIMITS: Dict[str, Dict[str, Any]] = {
    "sandboxed": {
        "cpu_sec_extra": 0,
        "as_bytes": 2 * 1024 ** 3,       # 2 GB
        "nproc": 32,
        "fsize_bytes": 512 * 1024 ** 2,   # 512 MB
    },
    "trusted": {
        "cpu_sec_extra": 30,
        "as_bytes": 4 * 1024 ** 3,        # 4 GB
        "nproc": 64,
        "fsize_bytes": 1 * 1024 ** 3,     # 1 GB
    },
    "template": {
        "cpu_sec_extra": 30,
        "as_bytes": 4 * 1024 ** 3,
        "nproc": 64,
        "fsize_bytes": 1 * 1024 ** 3,
    },
}


def make_preexec_fn(
    profile: str = "trusted", timeout_sec: int = 120
) -> Optional[Callable[[], None]]:
    """Return a preexec_fn that sets resource limits, or None on non-Unix."""
    if sys.platform == "win32":
        return None

    try:
        import resource  # Unix only
    except ImportError:
        return None

    limits = _RESOURCE_LIMITS.get(profile, _RESOURCE_LIMITS["trusted"])
    cpu_hard = max(1, timeout_sec + limits["cpu_sec_extra"])
    as_bytes = limits["as_bytes"]
    nproc = limits["nproc"]
    fsize = limits["fsize_bytes"]

    def _set_limits() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_hard, cpu_hard))
        resource.setrlimit(resource.RLIMIT_AS, (as_bytes, as_bytes))
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))

    return _set_limits


# ---------------------------------------------------------------------------
# Code pattern scanning (sandboxed profile only)
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bos\.system\s*\("), "os.system"),
    (re.compile(r"\bsubprocess\b"), "subprocess"),
    (re.compile(r"\bexec\s*\("), "exec()"),
    (re.compile(r"\beval\s*\("), "eval()"),
    (re.compile(r"\b__import__\s*\("), "__import__()"),
    (re.compile(r"\bsocket\b"), "socket"),
    (re.compile(r"\bshutil\.rmtree\b"), "shutil.rmtree"),
    (re.compile(r"\bos\.remove\b"), "os.remove"),
    (re.compile(r"\bos\.unlink\b"), "os.unlink"),
    (re.compile(r"\bctypes\b"), "ctypes"),
    (re.compile(r"\bos\.environ\b"), "os.environ"),
    (re.compile(r"\bos\.popen\b"), "os.popen"),
    (re.compile(r"\bos\.exec"), "os.exec*"),
    (re.compile(r"\bos\.spawn"), "os.spawn*"),
    (re.compile(r"\bos\.kill\b"), "os.kill"),
    (re.compile(r"\bsignal\."), "signal module"),
]


def scan_code_patterns(
    code: str, profile: str = "sandboxed"
) -> Optional[Dict[str, Any]]:
    """Scan code for dangerous patterns. Returns error dict or None if clean."""
    if profile != "sandboxed":
        return None

    violations: List[str] = []
    for pattern, label in _DANGEROUS_PATTERNS:
        if pattern.search(code):
            violations.append(label)

    if not violations:
        return None

    _log.warning(
        "chart sandbox code scan blocked %d pattern(s): %s",
        len(violations),
        ", ".join(violations),
    )
    return {
        "error": "code_scan_blocked",
        "violations": violations,
        "message": f"Code contains blocked patterns: {', '.join(violations)}",
    }


# ---------------------------------------------------------------------------
# Filesystem guard source (injected into sandboxed runner scripts)
# ---------------------------------------------------------------------------


def build_filesystem_guard_source(
    output_dir: str, allowed_roots: List[str]
) -> str:
    """Return Python source that monkey-patches builtins.open for sandboxed execution."""
    import json as _json

    output_dir_json = _json.dumps(output_dir)
    allowed_json = _json.dumps(allowed_roots)

    return (
        "import builtins as _builtins, os as _os\n"
        f"_FS_OUTPUT_DIR = {output_dir_json}\n"
        f"_FS_ALLOWED_ROOTS = {allowed_json}\n"
        "_original_open = _builtins.open\n"
        "def _guarded_open(file, mode='r', *a, **kw):\n"
        "    path = _os.path.realpath(str(file))\n"
        "    writing = any(c in str(mode) for c in 'wxa+')\n"
        "    if writing:\n"
        "        if not path.startswith(_os.path.realpath(_FS_OUTPUT_DIR)):\n"
        "            raise PermissionError(f'sandbox: write denied outside output dir: {path}')\n"
        "    else:\n"
        "        ok = any(path.startswith(_os.path.realpath(r)) for r in _FS_ALLOWED_ROOTS)\n"
        "        if not ok:\n"
        "            raise PermissionError(f'sandbox: read denied outside allowed roots: {path}')\n"
        "    return _original_open(file, mode, *a, **kw)\n"
        "_builtins.open = _guarded_open\n"
    )
