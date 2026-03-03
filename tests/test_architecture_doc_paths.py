from __future__ import annotations

from pathlib import Path


def test_module_boundaries_avoids_removed_student_shell_paths() -> None:
    doc = Path("docs/architecture/module-boundaries.md").read_text(encoding="utf-8")
    outdated_paths = [
        "frontend/apps/student/src/features/session/StudentSessionShell.tsx",
        "frontend/apps/student/src/features/chat/StudentChatPanel.tsx",
        "frontend/apps/student/src/features/workbench/StudentWorkbench.tsx",
    ]
    for path in outdated_paths:
        assert path not in doc, f"outdated path remains in architecture doc: {path}"
