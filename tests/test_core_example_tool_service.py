from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.core_example_tool_service import (
    CoreExampleToolDeps,
    core_example_register,
    core_example_render,
    core_example_search,
)


class CoreExampleToolServiceTest(unittest.TestCase):
    def _deps(self, root: Path):
        return CoreExampleToolDeps(
            data_dir=root / "data",
            app_root=root,
            is_safe_tool_id=lambda value: bool(str(value or "").strip()) and "/" not in str(value),
            resolve_app_path=lambda value, must_exist=True: (
                Path(value) if (not must_exist or Path(value).exists()) else None
            ),
            run_script=lambda cmd: {"cmd": cmd},
        )

    def test_core_example_search_filters_rows(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "data" / "core_examples" / "examples.csv"
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["kp_id", "example_id"])
                writer.writeheader()
                writer.writerow({"kp_id": "KP1", "example_id": "E1"})
                writer.writerow({"kp_id": "KP2", "example_id": "E2"})
            deps = self._deps(root)
            result = core_example_search({"kp_id": "KP1"}, deps=deps)
            items = result.get("examples") or []
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["example_id"], "E1")

    def test_core_example_register_validates_and_rejects_bad_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            invalid = core_example_register({"example_id": "", "kp_id": "KP1", "core_model": "M"}, deps=deps)
            self.assertEqual(invalid.get("error"), "invalid_example_id")

            bad_path = core_example_register(
                {
                    "example_id": "E1",
                    "kp_id": "KP1",
                    "core_model": "M",
                    "stem_file": str(root / "missing.md"),
                },
                deps=deps,
            )
            self.assertEqual(bad_path.get("error"), "stem_file_not_found_or_outside_app_root")

    def test_core_example_render_validates_example_id(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            result = core_example_render({"example_id": ""}, deps=deps)
            self.assertEqual(result.get("error"), "invalid_example_id")


if __name__ == "__main__":
    unittest.main()
