from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATHS = (
    Path("frontend/vite.config.ts"),
    Path("frontend/vite.teacher.config.ts"),
    Path("frontend/vite.student.config.ts"),
)


def test_pwa_configs_inline_workbox_runtime() -> None:
    for config_path in _CONFIG_PATHS:
        source = config_path.read_text(encoding="utf-8")
        assert "inlineWorkboxRuntime: true" in source, (
            f"{config_path.name} should set workbox.inlineWorkboxRuntime to true "
            "so Workbox does not trigger the Rollup manualChunks warning during build."
        )


def test_frontend_uses_vitest_v4_with_vite_v7() -> None:
    package_json = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    version = str((package_json.get("devDependencies") or {}).get("vitest") or "")
    assert version.startswith("^4."), (
        "frontend should keep vitest on v4 so the test toolchain stays aligned with Vite 7 "
        "instead of pulling in an extra Vite 5 dependency tree with known advisories."
    )
