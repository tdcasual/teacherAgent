from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_admin_manager_resolves_symlink_entrypoint(tmp_path: Path) -> None:
    source_script = Path("scripts/admin_manager").read_text(encoding="utf-8")

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    manager = scripts_dir / "admin_manager"
    manager.write_text(source_script, encoding="utf-8")
    manager.chmod(0o755)

    auth_tui = scripts_dir / "admin_auth_tui.py"
    auth_tui.write_text(
        "import json, sys\n"
        "import services\n"
        "print(json.dumps({'argv': sys.argv[1:], 'services': services.__name__}))\n",
        encoding="utf-8",
    )
    auth_tui.chmod(0o755)

    services_pkg = tmp_path / "services"
    services_pkg.mkdir(parents=True, exist_ok=True)
    (services_pkg / "__init__.py").write_text("", encoding="utf-8")

    other_cwd = tmp_path / "other"
    other_cwd.mkdir(parents=True, exist_ok=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    symlink_entry = bin_dir / "admin_manager"
    symlink_entry.symlink_to(manager)

    result = subprocess.run(
        [str(symlink_entry), "list", "--limit", "1"],
        cwd=str(other_cwd),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout.strip())
    assert payload["services"] == "services"
    assert payload["argv"] == ["--trusted-local", "list", "--limit", "1"]
