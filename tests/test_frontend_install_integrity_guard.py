from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND = _ROOT / "frontend"
_GUARD_SCRIPT = _FRONTEND / "scripts" / "check_types_install_integrity.mjs"
_PACKAGE_JSON = _FRONTEND / "package.json"


def _run_guard(types_dir: Path) -> subprocess.CompletedProcess[str]:
    node_bin = shutil.which("node")
    assert node_bin, "node binary is required for frontend guard tests"
    return subprocess.run(
        [node_bin, str(_GUARD_SCRIPT), "--types-dir", str(types_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_frontend_guard_script_exists() -> None:
    assert _GUARD_SCRIPT.exists(), (
        "frontend install integrity guard must exist at "
        "frontend/scripts/check_types_install_integrity.mjs"
    )


def test_guard_accepts_clean_types_tree(tmp_path: Path) -> None:
    types_dir = tmp_path / "@types"
    types_dir.mkdir(parents=True)
    (types_dir / "react").mkdir()
    (types_dir / "react-dom").mkdir()

    proc = _run_guard(types_dir)
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_guard_rejects_suffix_polluted_types_tree(tmp_path: Path) -> None:
    types_dir = tmp_path / "@types"
    types_dir.mkdir(parents=True)
    (types_dir / "react").mkdir()
    (types_dir / "react 3").mkdir()

    proc = _run_guard(types_dir)
    assert proc.returncode != 0
    output = f"{proc.stdout}\n{proc.stderr}"
    assert "react 3" in output


def test_frontend_package_scripts_enforce_guard_and_verify_chain() -> None:
    payload = json.loads(_PACKAGE_JSON.read_text(encoding="utf-8"))
    scripts = payload.get("scripts") or {}
    assert scripts.get("check:types-install") == "node scripts/check_types_install_integrity.mjs"

    typecheck = str(scripts.get("typecheck") or "")
    assert "check:types-install" in typecheck
    assert "tsc -p tsconfig.json --noEmit" in typecheck

    verify = str(scripts.get("verify") or "")
    assert "npm run lint" in verify
    assert "npm run format:check" in verify
    assert "npm run typecheck" in verify
    assert "npm run build:teacher" in verify
    assert "npm run build:student" in verify
