from __future__ import annotations

import hashlib
import json
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def _clip_text(value: str) -> str:
    if len(value) <= _MAX_STD_CHARS:
        return value
    return value[:_MAX_STD_CHARS] + "\n...[truncated]..."


def _normalize_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except Exception:
        return _DEFAULT_TIMEOUT_SEC
    if timeout <= 0:
        return _DEFAULT_TIMEOUT_SEC
    return min(timeout, _MAX_TIMEOUT_SEC)


def _normalize_retries(value: Any) -> int:
    try:
        retries = int(value)
    except Exception:
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
        return {"ok": False, "error": str(exc), "packages": packages}
    return {
        "ok": proc.returncode == 0,
        "packages": packages,
        "exit_code": int(proc.returncode),
        "stdout": _clip_text(proc.stdout or ""),
        "stderr": _clip_text(proc.stderr or ""),
    }


def _build_runner_source(python_code: str, input_payload: Any, output_dir: Path, main_image: Path) -> str:
    input_json = json.dumps(input_payload, ensure_ascii=False)
    input_json_text = json.dumps(input_json, ensure_ascii=False)
    output_dir_json = json.dumps(str(output_dir))
    main_image_json = json.dumps(str(main_image))
    code_json = json.dumps(python_code, ensure_ascii=False)
    return (
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
        "ENV = {\n"
        "    'input_data': INPUT_DATA,\n"
        "    'plt': plt,\n"
        "    'np': np,\n"
        "    'pd': pd,\n"
        "    'sns': sns,\n"
        "    'save_chart': save_chart,\n"
        "    'save_text': save_text,\n"
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
    python_code = str(args.get("python_code") or "")
    if not python_code.strip():
        return {"error": "missing_python_code"}

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

    script_source = _build_runner_source(python_code, input_data, output_dir, main_image)
    script_path.write_text(script_source, encoding="utf-8")
    try:
        (run_dir / "input.json").write_text(json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        (run_dir / "input.json").write_text("null\n", encoding="utf-8")

    started_at = _iso_now()
    python_exec = "python3"
    env_dir: Optional[Path] = None
    installed_packages: List[str] = []
    install_logs: List[Dict[str, Any]] = []
    attempts: List[Dict[str, Any]] = []
    timed_out = False
    exit_code = -1
    stdout = ""
    stderr = ""

    if auto_install:
        env_scope = _venv_scope(requested_packages)
        env_dir = _env_root(uploads_dir, env_scope)
        venv_result = _ensure_venv(env_dir)
        if not venv_result.get("ok"):
            error_payload = {
                "error": "venv_init_failed",
                "run_id": run_id,
                "detail": venv_result,
                "meta_url": f"/chart-runs/{run_id}/meta",
            }
            meta_path.write_text(json.dumps({"run_id": run_id, "ok": False, **error_payload}, ensure_ascii=False, indent=2), encoding="utf-8")
            return error_payload
        python_exec = str(venv_result.get("python") or _env_python_path(env_dir))
        if requested_packages:
            pre_install = _pip_install(python_exec, requested_packages, timeout_sec=max(120, timeout_sec * 4))
            install_logs.append({"phase": "requested_packages", **pre_install})
            if pre_install.get("ok"):
                installed_packages.extend(requested_packages)

    auto_installed_missing: set[str] = set()
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

    ok = (exit_code == 0) and bool(image_url)
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
        "auto_install": auto_install,
        "requested_packages": requested_packages,
        "installed_packages": installed_packages,
        "install_logs": install_logs,
        "attempts": attempts,
        "stdout_file": str(stdout_path),
        "stderr_file": str(stderr_path),
        "image_url": image_url,
        "artifacts": artifacts,
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
        "stdout": stdout,
        "stderr": stderr,
        "python_executable": python_exec,
        "environment_dir": str(env_dir) if env_dir else None,
        "auto_install": auto_install,
        "requested_packages": requested_packages,
        "installed_packages": installed_packages,
        "install_logs": install_logs,
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
