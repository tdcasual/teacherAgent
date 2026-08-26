from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .env_service import _env_python_path, _env_root, _scope_from_env_dir, _venv_scope
from .host import host_call
from .normalize import (
    _clip_text,
    _extract_missing_module,
    _format_artifacts_markdown,
    _iso_now,
    _normalize_bool,
    _normalize_packages,
    _normalize_retries,
    _normalize_timeout,
    _safe_file_name,
)

_log = logging.getLogger(__name__)


def execute_with_global_semaphore(
    *,
    exec_args: Dict[str, Any],
    app_root: Path,
    uploads_dir: Path,
    python_code: str,
    execution_profile: str,
    audit_context: Dict[str, str],
    trusted_alerts: List[str],
    execute_inner: Callable[[Dict[str, Any], Path, Path, str, str], Dict[str, Any]],
    audit_log: Callable[[str, Dict[str, Any]], None],
    semaphore: Any,
    acquire_timeout_sec: float = 30.0,
) -> Dict[str, Any]:
    acquired = semaphore.acquire(timeout=acquire_timeout_sec)
    if not acquired:
        return {"error": "chart_exec_busy", "message": "Too many concurrent chart executions"}

    try:
        result = execute_inner(
            exec_args,
            app_root,
            uploads_dir,
            python_code,
            execution_profile,
        )
        audit_log(
            "chart.exec.finish",
            {
                "execution_profile": execution_profile,
                "source": audit_context.get("source"),
                "role": audit_context.get("role"),
                "actor": audit_context.get("actor"),
                "ok": bool(result.get("ok")),
                "run_id": result.get("run_id"),
                "exit_code": result.get("exit_code"),
                "timed_out": bool(result.get("timed_out")),
                "auto_install": bool(result.get("auto_install")),
                "requested_packages": result.get("requested_packages") or [],
                "installed_packages": result.get("installed_packages") or [],
                "trusted_risk_alerts": trusted_alerts,
            },
        )
        return result
    finally:
        semaphore.release()


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
        "os.environ.setdefault('MPLCONFIGDIR', os.path.join(OUTPUT_DIR, '.mplconfig'))\n"
        "os.makedirs(os.environ['MPLCONFIGDIR'], exist_ok=True)\n"
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


def _chart_exec_audit_details(args: Dict[str, Any]) -> Dict[str, Any]:
    raw_audit = args.get("_audit_context") if isinstance(args, dict) else None
    audit_context = raw_audit if isinstance(raw_audit, dict) else {}
    trusted_risk_alerts = args.get("_trusted_risk_alerts")
    return {
        "source": str(audit_context.get("source") or "unknown").strip().lower() or "unknown",
        "role": str(audit_context.get("role") or "").strip().lower(),
        "actor": str(audit_context.get("actor") or "").strip(),
        "trusted_risk_alerts": trusted_risk_alerts if isinstance(trusted_risk_alerts, list) else [],
    }


def _prepare_chart_exec_paths(uploads_dir: Path, *, run_id: str, save_as: str) -> Dict[str, Path]:
    chart_root = uploads_dir / "charts"
    run_root = uploads_dir / "chart_runs"
    output_dir = chart_root / run_id
    run_dir = run_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    return {
        "output_dir": output_dir,
        "run_dir": run_dir,
        "main_image": output_dir / save_as,
        "script_path": run_dir / "run.py",
        "stdout_path": run_dir / "stdout.txt",
        "stderr_path": run_dir / "stderr.txt",
        "meta_path": run_dir / "meta.json",
    }


def _write_chart_exec_script(
    *,
    python_code: str,
    input_data: Any,
    execution_profile: str,
    uploads_dir: Path,
    output_dir: Path,
    main_image: Path,
    script_path: Path,
    build_filesystem_guard_source: Any,
) -> None:
    fs_guard = ""
    if execution_profile == "sandboxed":
        fs_guard = build_filesystem_guard_source(
            str(output_dir),
            [str(output_dir), str(uploads_dir)],
        )
    script_source = _build_runner_source(
        python_code,
        input_data,
        output_dir,
        main_image,
        filesystem_guard=fs_guard,
    )
    script_path.write_text(script_source, encoding="utf-8")


def _write_chart_input_snapshot(*, run_dir: Path, input_data: Any, run_id: str) -> None:
    try:
        (run_dir / "input.json").write_text(
            json.dumps(input_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to serialize input_data for run %s, writing null", run_id)
        (run_dir / "input.json").write_text("null\n", encoding="utf-8")


def _chart_venv_init_failed_payload(
    *,
    run_id: str,
    detail: Dict[str, Any],
    environment_scope: str,
    env_gc: Dict[str, Any],
    execution_profile: str,
    audit: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "error": "venv_init_failed",
        "run_id": run_id,
        "detail": detail,
        "environment_scope": environment_scope,
        "env_gc": env_gc,
        "meta_url": f"/chart-runs/{run_id}/meta",
        "execution_profile": execution_profile,
        "audit": {
            "source": audit.get("source"),
            "role": audit.get("role"),
            "actor": audit.get("actor"),
            "trusted_risk_alerts": audit.get("trusted_risk_alerts") or [],
        },
    }


def _init_chart_exec_environment(
    *,
    auto_install: bool,
    requested_packages: List[str],
    uploads_dir: Path,
    timeout_sec: int,
    run_id: str,
    meta_path: Path,
    execution_profile: str,
    audit: Dict[str, Any],
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "python_exec": "python3",
        "env_scope": None,
        "env_dir": None,
        "lease_path": None,
        "installed_packages": [],
        "install_logs": [],
        "env_gc": {"enabled": False, "skipped": "auto_install_disabled"},
        "error_payload": None,
    }
    if not auto_install:
        return state

    env_scope = _venv_scope(requested_packages)
    state["env_scope"] = env_scope
    try:
        state["env_gc"] = host_call("_maybe_prune_chart_envs", uploads_dir, keep_scopes={env_scope})
    except Exception as exc:  # policy: allowed-broad-except
        _log.debug("operation failed", exc_info=True)
        state["env_gc"] = {"enabled": True, "error": "gc_failed", "detail": str(exc)}

    env_dir = _env_root(uploads_dir, env_scope)
    state["env_dir"] = env_dir
    venv_result = host_call("_ensure_venv", env_dir)
    if not venv_result.get("ok"):
        payload = _chart_venv_init_failed_payload(
            run_id=run_id,
            detail=venv_result,
            environment_scope=env_scope,
            env_gc=state["env_gc"],
            execution_profile=execution_profile,
            audit=audit,
        )
        meta_path.write_text(
            json.dumps({"run_id": run_id, "ok": False, **payload}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        state["error_payload"] = payload
        return state

    state["python_exec"] = str(venv_result.get("python") or _env_python_path(env_dir))
    try:
        host_call("_mark_chart_env_used", env_dir, scope=env_scope, packages=requested_packages)
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to mark chart env used for scope %s", env_scope)
        pass  # policy: allowed-broad-except
    try:
        state["lease_path"] = host_call("_acquire_chart_env_lease", env_dir, run_id)
    except Exception:  # policy: allowed-broad-except
        _log.warning("failed to acquire chart env lease for run %s", run_id, exc_info=True)
        state["lease_path"] = None

    if requested_packages:
        pre_install = host_call(
            "_pip_install",
            state["python_exec"],
            requested_packages,
            timeout_sec=max(120, timeout_sec * 4),
        )
        state["install_logs"].append({"phase": "requested_packages", **pre_install})
        if pre_install.get("ok"):
            state["installed_packages"].extend(requested_packages)
    return state


def _snapshot_cwd_files(app_root: Path) -> set[str]:
    try:
        return {e.name for e in os.scandir(str(app_root)) if e.is_file(follow_symlinks=False)}
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to snapshot cwd before execution")
        return set()


def _run_chart_subprocess_once(
    *,
    python_exec: str,
    script_path: Path,
    cwd_dir: Path,
    timeout_sec: int,
    sandbox_env: Dict[str, str],
    sandbox_preexec: Any,
) -> Dict[str, Any]:
    timed_out = False
    exit_code = -1
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            [python_exec, str(script_path)],
            cwd=str(cwd_dir),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=sandbox_env,
            preexec_fn=sandbox_preexec,
        )
        exit_code = int(proc.returncode)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        stderr = (stderr + "\nprocess timed out").strip()
    except Exception as exc:  # policy: allowed-broad-except
        _log.debug("operation failed", exc_info=True)
        stderr = str(exc)
    return {
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout": _clip_text(stdout),
        "stderr": _clip_text(stderr),
    }


def _maybe_install_missing_module(
    *,
    attempt: int,
    exec_retries: int,
    auto_install: bool,
    stderr: str,
    auto_installed_missing: set[str],
    python_exec: str,
    timeout_sec: int,
    install_logs: List[Dict[str, Any]],
    installed_packages: List[str],
) -> bool:
    missing_module = _extract_missing_module(stderr)
    if not (
        auto_install
        and (attempt < exec_retries)
        and missing_module
        and (missing_module not in auto_installed_missing)
    ):
        return False

    auto_installed_missing.add(missing_module)
    install_res = host_call(
        "_pip_install",
        python_exec,
        [missing_module],
        timeout_sec=max(120, timeout_sec * 3),
    )
    install_logs.append({"phase": f"missing_module_attempt_{attempt}", **install_res})
    if not install_res.get("ok"):
        return False
    if missing_module.lower() not in {p.lower() for p in installed_packages}:
        installed_packages.append(missing_module)
    return True


def _run_chart_exec_with_retries(
    *,
    python_exec: str,
    script_path: Path,
    cwd_dir: Path,
    timeout_sec: int,
    exec_retries: int,
    execution_profile: str,
    auto_install: bool,
    install_logs: List[Dict[str, Any]],
    installed_packages: List[str],
    build_sanitized_env: Any,
    make_preexec_fn: Any,
) -> Dict[str, Any]:
    sandbox_env = build_sanitized_env(execution_profile)
    sandbox_preexec = make_preexec_fn(execution_profile, timeout_sec)
    auto_installed_missing: set[str] = set()
    attempts: List[Dict[str, Any]] = []
    exit_code = -1
    timed_out = False
    stdout = ""
    stderr = ""
    for attempt in range(1, exec_retries + 1):
        attempt_result = _run_chart_subprocess_once(
            python_exec=python_exec,
            script_path=script_path,
            cwd_dir=cwd_dir,
            timeout_sec=timeout_sec,
            sandbox_env=sandbox_env,
            sandbox_preexec=sandbox_preexec,
        )
        attempts.append({"attempt": attempt, **attempt_result})
        exit_code = int(attempt_result["exit_code"])
        timed_out = bool(attempt_result["timed_out"])
        stdout = str(attempt_result["stdout"] or "")
        stderr = str(attempt_result["stderr"] or "")
        if exit_code == 0:
            break
        should_retry = _maybe_install_missing_module(
            attempt=attempt,
            exec_retries=exec_retries,
            auto_install=auto_install,
            stderr=stderr,
            auto_installed_missing=auto_installed_missing,
            python_exec=python_exec,
            timeout_sec=timeout_sec,
            install_logs=install_logs,
            installed_packages=installed_packages,
        )
        if should_retry:
            continue
        break
    return {
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "attempts": attempts,
    }


def _capture_new_cwd_files(*, app_root: Path, output_dir: Path, cwd_before: set[str]) -> None:
    try:
        cwd_after = {e.name for e in os.scandir(str(app_root)) if e.is_file(follow_symlinks=False)}
        new_files = cwd_after - cwd_before
        for fname in sorted(new_files):
            src = app_root / fname
            dst = output_dir / fname
            if dst.exists():
                continue
            try:
                shutil.copy2(str(src), str(dst))
                _log.debug("captured new cwd file %s → %s", fname, dst)
            except Exception:  # policy: allowed-broad-except
                _log.debug("failed to capture cwd file %s", fname)
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to scan cwd for new files after execution")


def _collect_chart_artifacts(output_dir: Path, *, run_id: str) -> Dict[str, Any]:
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
    return {"artifacts": artifacts, "image_url": image_url}


def _chart_exec_audit_payload(audit: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": audit.get("source"),
        "role": audit.get("role"),
        "actor": audit.get("actor"),
        "trusted_risk_alerts": audit.get("trusted_risk_alerts") or [],
    }


def _execute_chart_exec_inner(
    args: Dict[str, Any],
    app_root: Path,
    uploads_dir: Path,
    python_code: str,
    execution_profile: str,
) -> Dict[str, Any]:
    from ..chart_sandbox import (
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
    audit = _chart_exec_audit_details(args)

    paths = _prepare_chart_exec_paths(uploads_dir, run_id=run_id, save_as=save_as)
    output_dir = paths["output_dir"]
    run_dir = paths["run_dir"]
    main_image = paths["main_image"]
    script_path = paths["script_path"]
    stdout_path = paths["stdout_path"]
    stderr_path = paths["stderr_path"]
    meta_path = paths["meta_path"]
    _write_chart_exec_script(
        python_code=python_code,
        input_data=input_data,
        execution_profile=execution_profile,
        uploads_dir=uploads_dir,
        output_dir=output_dir,
        main_image=main_image,
        script_path=script_path,
        build_filesystem_guard_source=build_filesystem_guard_source,
    )
    _write_chart_input_snapshot(run_dir=run_dir, input_data=input_data, run_id=run_id)

    started_at = _iso_now()
    env_state = _init_chart_exec_environment(
        auto_install=auto_install,
        requested_packages=requested_packages,
        uploads_dir=uploads_dir,
        timeout_sec=timeout_sec,
        run_id=run_id,
        meta_path=meta_path,
        execution_profile=execution_profile,
        audit=audit,
    )
    python_exec = str(env_state.get("python_exec") or "python3")
    env_scope = env_state.get("env_scope")
    env_dir = env_state.get("env_dir")
    lease_path = env_state.get("lease_path")
    installed_packages: List[str] = list(env_state.get("installed_packages") or [])
    install_logs: List[Dict[str, Any]] = list(env_state.get("install_logs") or [])
    env_gc: Dict[str, Any] = dict(env_state.get("env_gc") or {})
    timed_out = False
    exit_code = -1
    stdout = ""
    stderr = ""
    attempts: List[Dict[str, Any]] = []
    cwd_before: set[str] = set()
    try:
        error_payload = env_state.get("error_payload")
        if isinstance(error_payload, dict):
            return error_payload
        cwd_before = _snapshot_cwd_files(app_root)
        run_state = _run_chart_exec_with_retries(
            python_exec=python_exec,
            script_path=script_path,
            cwd_dir=output_dir,
            timeout_sec=timeout_sec,
            exec_retries=exec_retries,
            execution_profile=execution_profile,
            auto_install=auto_install,
            install_logs=install_logs,
            installed_packages=installed_packages,
            build_sanitized_env=build_sanitized_env,
            make_preexec_fn=make_preexec_fn,
        )
        timed_out = bool(run_state.get("timed_out"))
        run_exit_code = run_state.get("exit_code")
        exit_code = int(run_exit_code) if run_exit_code is not None else -1
        stdout = str(run_state.get("stdout") or "")
        stderr = str(run_state.get("stderr") or "")
        attempts = list(run_state.get("attempts") or [])
    finally:
        host_call("_release_chart_env_lease", lease_path if isinstance(lease_path, Path) else None)
        if isinstance(env_dir, Path):
            try:
                host_call(
                    "_mark_chart_env_used",
                    env_dir,
                    scope=str(env_scope or _scope_from_env_dir(env_dir)),
                    packages=requested_packages,
                )
            except Exception:  # policy: allowed-broad-except
                _log.debug("failed to mark chart env used in finally for scope %s", env_scope)
                pass  # policy: allowed-broad-except

    _capture_new_cwd_files(app_root=app_root, output_dir=output_dir, cwd_before=cwd_before)
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    artifact_state = _collect_chart_artifacts(output_dir, run_id=run_id)
    artifacts: List[Dict[str, Any]] = list(artifact_state["artifacts"])
    image_url = artifact_state["image_url"]
    ok = (exit_code == 0) and (bool(image_url) or bool(artifacts))
    artifacts_markdown = _format_artifacts_markdown(artifacts)
    finished_at = _iso_now()
    audit_payload = _chart_exec_audit_payload(audit)
    meta = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "execution_profile": execution_profile,
        "timeout_sec": timeout_sec,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "ok": ok,
        "chart_hint": chart_hint,
        "script": str(script_path),
        "output_dir": str(output_dir),
        "python_executable": python_exec,
        "environment_dir": str(env_dir) if isinstance(env_dir, Path) else None,
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
        "audit": audit_payload,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": ok,
        "run_id": run_id,
        "execution_profile": execution_profile,
        "timed_out": timed_out,
        "timeout_sec": timeout_sec,
        "exit_code": exit_code,
        "image_url": image_url,
        "artifacts": artifacts,
        "artifacts_markdown": artifacts_markdown,
        "stdout": stdout,
        "stderr": stderr,
        "python_executable": python_exec,
        "environment_dir": str(env_dir) if isinstance(env_dir, Path) else None,
        "environment_scope": env_scope,
        "auto_install": auto_install,
        "requested_packages": requested_packages,
        "installed_packages": installed_packages,
        "install_logs": install_logs,
        "env_gc": env_gc,
        "attempts": attempts,
        "audit": audit_payload,
        "meta_url": f"/chart-runs/{run_id}/meta",
    }

