from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.student_persona_api_service import StudentPersonaApiDeps, student_personas_get_api
from services.api.teacher_persona_api_service import (
    TeacherPersonaApiDeps,
    teacher_persona_assign_api,
    teacher_persona_create_api,
    teacher_persona_update_api,
    teacher_persona_visibility_api,
    teacher_personas_get_api,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class TeacherPersonaApiServiceTest(unittest.TestCase):
    def _teacher_deps(self, root: Path) -> TeacherPersonaApiDeps:
        return TeacherPersonaApiDeps(
            data_dir=root / "data",
            now_iso=lambda: "2026-02-13T14:00:00",
        )

    def _student_deps(self, root: Path) -> StudentPersonaApiDeps:
        return StudentPersonaApiDeps(
            data_dir=root / "data",
            now_iso=lambda: "2026-02-13T14:00:00",
        )

    def test_create_and_update_teacher_persona(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._teacher_deps(root)

            created = teacher_persona_create_api(
                "T001",
                {
                    "name": "林黛玉风格",
                    "summary": "温柔细腻",
                    "style_rules": ["先肯定后追问"],
                    "few_shot_examples": ["你这个思路很细，我再追问一步。"],
                    "visibility_mode": "assigned_only",
                },
                deps=deps,
            )
            assert created["ok"] is True
            pid = created["persona"]["persona_id"]

            updated = teacher_persona_update_api(
                "T001",
                pid,
                {"summary": "温柔细腻、循循善诱"},
                deps=deps,
            )
            assert updated["ok"] is True
            assert updated["persona"]["summary"] == "温柔细腻、循循善诱"

            listing = teacher_personas_get_api("T001", deps=deps)
            assert listing["ok"] is True
            assert len(listing["personas"]) == 1

    def test_assign_to_student_and_student_can_see(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            tdeps = self._teacher_deps(root)
            sdeps = self._student_deps(root)

            created = teacher_persona_create_api(
                "T001",
                {
                    "name": "理性引导",
                    "style_rules": ["每次只推进一小步"],
                    "few_shot_examples": ["先写已知量。"],
                },
                deps=tdeps,
            )
            pid = created["persona"]["persona_id"]

            assigned = teacher_persona_assign_api(
                "T001",
                pid,
                {"student_id": "S001", "status": "active"},
                deps=tdeps,
            )
            assert assigned["ok"] is True

            student_view = student_personas_get_api("S001", deps=sdeps)
            assert student_view["ok"] is True
            assert any(item.get("persona_id") == pid for item in student_view["assigned"])

    def test_hidden_all_persona_not_visible_to_student(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            tdeps = self._teacher_deps(root)
            sdeps = self._student_deps(root)

            created = teacher_persona_create_api(
                "T001",
                {
                    "name": "保密角色",
                    "style_rules": ["简洁"],
                    "few_shot_examples": ["先判断受力。"],
                },
                deps=tdeps,
            )
            pid = created["persona"]["persona_id"]
            teacher_persona_assign_api("T001", pid, {"student_id": "S001", "status": "active"}, deps=tdeps)
            teacher_persona_visibility_api(
                "T001",
                pid,
                {"visibility_mode": "hidden_all"},
                deps=tdeps,
            )

            student_view = student_personas_get_api("S001", deps=sdeps)
            assert student_view["ok"] is True
            assert not any(item.get("persona_id") == pid for item in student_view["assigned"])


if __name__ == "__main__":
    unittest.main()

