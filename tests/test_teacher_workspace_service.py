from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_workspace_service import TeacherWorkspaceDeps, ensure_teacher_workspace


class TeacherWorkspaceServiceTest(unittest.TestCase):
    def test_ensure_teacher_workspace_creates_expected_files(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            def workspace_dir(teacher_id: str) -> Path:
                return root / teacher_id

            def memory_dir(teacher_id: str) -> Path:
                return root / teacher_id / "memory"

            deps = TeacherWorkspaceDeps(
                teacher_workspace_dir=workspace_dir,
                teacher_daily_memory_dir=memory_dir,
            )
            base = ensure_teacher_workspace("teacher_a", deps=deps)

            self.assertTrue(base.exists())
            self.assertTrue((base / "proposals").exists())
            self.assertTrue((base / "memory").exists())
            for name in ("AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"):
                self.assertTrue((base / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
