from __future__ import annotations

import json
import logging
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.student_persona_api_service import (
    StudentPersonaApiDeps,
    resolve_student_persona_runtime,
    student_persona_avatar_upload_api,
    student_persona_activate_api,
    student_persona_custom_update_api,
    student_persona_custom_create_api,
    student_persona_custom_delete_api,
    student_personas_get_api,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class StudentPersonaApiServiceTest(unittest.TestCase):
    def _deps(self, root: Path) -> StudentPersonaApiDeps:
        return StudentPersonaApiDeps(
            data_dir=root / "data",
            uploads_dir=root / "uploads",
            now_iso=lambda: "2026-02-13T12:00:00",
        )

    def test_get_personas_merges_assigned_and_custom(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            _write_json(
                root / "data" / "persona_assignments" / "by_student" / "S001.json",
                {
                    "assignments": [
                        {"teacher_id": "T001", "persona_id": "preset_1", "status": "active"},
                    ]
                },
            )
            _write_json(
                root / "data" / "teacher_personas" / "T001" / "personas.json",
                {
                    "personas": [
                        {
                            "persona_id": "preset_1",
                            "name": "林风",
                            "summary": "温柔启发式",
                            "style_rules": ["先肯定后引导"],
                            "few_shot_examples": ["我们先看你这一步很接近了。"],
                            "lifecycle_status": "active",
                            "visibility_mode": "assigned_only",
                        }
                    ]
                },
            )
            _write_json(
                root / "data" / "student_profiles" / "S001.json",
                {
                    "student_id": "S001",
                    "personas": {
                        "active_persona_id": "preset_1",
                        "custom": [
                            {
                                "persona_id": "custom_1",
                                "name": "自定义A",
                                "style_rules": ["句子短"],
                                "few_shot_examples": ["先写已知，再列方程。"],
                                "review_status": "approved",
                            }
                        ],
                    },
                },
            )

            data = student_personas_get_api("S001", deps=deps)
            assert data["ok"] is True
            assert data["student_id"] == "S001"
            assert data["active_persona_id"] == "preset_1"
            assert len(data["assigned"]) == 1
            assert data["assigned"][0]["persona_id"] == "preset_1"
            assert len(data["custom"]) == 1
            assert data["custom"][0]["persona_id"] == "custom_1"

    def test_custom_create_rejects_when_approved_limit_reached(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            _write_json(
                root / "data" / "student_profiles" / "S001.json",
                {
                    "student_id": "S001",
                    "personas": {
                        "custom": [
                            {"persona_id": f"c{i}", "name": f"N{i}", "review_status": "approved"}
                            for i in range(1, 6)
                        ]
                    },
                },
            )

            data = student_persona_custom_create_api(
                "S001",
                {
                    "name": "new_one",
                    "style_rules": ["温和"],
                    "few_shot_examples": ["我们一步步来。"],
                },
                deps=deps,
            )
            assert data["ok"] is False
            assert data["error"] == "custom_persona_limit_reached"

    def test_activate_and_delete_custom_persona(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            _write_json(
                root / "data" / "student_profiles" / "S001.json",
                {
                    "student_id": "S001",
                    "personas": {
                        "active_persona_id": "",
                        "custom": [
                            {
                                "persona_id": "custom_1",
                                "name": "自定义A",
                                "review_status": "approved",
                                "style_rules": ["温和"],
                                "few_shot_examples": ["先看题干。"],
                            }
                        ],
                    },
                },
            )

            activated = student_persona_activate_api("S001", "custom_1", deps=deps)
            assert activated["ok"] is True
            assert activated["active_persona_id"] == "custom_1"

            deleted = student_persona_custom_delete_api("S001", "custom_1", deps=deps)
            assert deleted["ok"] is True
            assert deleted["removed"] is True
            listing = student_personas_get_api("S001", deps=deps)
            assert listing["active_persona_id"] == ""
            assert listing["custom"] == []

    def test_runtime_resolve_marks_first_notice_once(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            _write_json(
                root / "data" / "teacher_personas" / "T001" / "personas.json",
                {
                    "personas": [
                        {
                            "persona_id": "preset_1",
                            "name": "林黛玉风格",
                            "summary": "细腻启发式",
                            "style_rules": ["先肯定后引导"],
                            "few_shot_examples": ["你这一步很细，我们再走半步。"],
                            "lifecycle_status": "active",
                            "visibility_mode": "assigned_only",
                        }
                    ]
                },
            )
            _write_json(
                root / "data" / "persona_assignments" / "by_student" / "S001.json",
                {
                    "assignments": [
                        {"teacher_id": "T001", "persona_id": "preset_1", "status": "active"},
                    ]
                },
            )
            _write_json(
                root / "data" / "student_profiles" / "S001.json",
                {"student_id": "S001", "personas": {"first_activation_notified_ids": []}},
            )

            first = resolve_student_persona_runtime("S001", "preset_1", deps=deps)
            assert first["ok"] is True
            assert first["first_notice"] is True
            assert "虚拟风格卡" in str(first["persona_prompt"])

            second = resolve_student_persona_runtime("S001", "preset_1", deps=deps)
            assert second["ok"] is True
            assert second["first_notice"] is False

    def test_student_custom_persona_avatar_upload_updates_avatar_url(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            _write_json(
                root / "data" / "student_profiles" / "S001.json",
                {
                    "student_id": "S001",
                    "personas": {
                        "custom": [
                            {
                                "persona_id": "custom_1",
                                "name": "自定义A",
                                "review_status": "approved",
                                "style_rules": ["温和"],
                                "few_shot_examples": ["先看题干。"],
                            }
                        ]
                    },
                },
            )
            uploaded = student_persona_avatar_upload_api(
                "S001",
                "custom_1",
                filename="avatar.webp",
                content=b"RIFFtestWEBPVP8 ",
                deps=deps,
            )
            assert uploaded["ok"] is True
            assert uploaded["avatar_url"].startswith("/student/personas/avatar/")
            listing = student_personas_get_api("S001", deps=deps)
            custom = next(item for item in listing["custom"] if item["persona_id"] == "custom_1")
            assert custom.get("avatar_url") == uploaded["avatar_url"]

    def test_student_custom_persona_update_changes_fields(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            _write_json(
                root / "data" / "student_profiles" / "S001.json",
                {
                    "student_id": "S001",
                    "personas": {
                        "custom": [
                            {
                                "persona_id": "custom_1",
                                "name": "原始名",
                                "summary": "原始摘要",
                                "review_status": "approved",
                                "style_rules": ["温和"],
                                "few_shot_examples": ["先看题干。"],
                            }
                        ]
                    },
                },
            )
            updated = student_persona_custom_update_api(
                "S001",
                "custom_1",
                {
                    "name": "新名字",
                    "summary": "新摘要",
                    "style_rules": ["先肯定再追问"],
                    "few_shot_examples": ["你这步很接近，我们再推进一步。"],
                },
                deps=deps,
            )
            assert updated["ok"] is True
            assert updated["persona"]["name"] == "新名字"
            listing = student_personas_get_api("S001", deps=deps)
            custom = next(item for item in listing["custom"] if item["persona_id"] == "custom_1")
            assert custom.get("summary") == "新摘要"

    def test_student_persona_create_rejects_overlong_fields(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            created = student_persona_custom_create_api(
                "S001",
                {
                    "name": "n" * 81,
                    "summary": "s" * 501,
                    "style_rules": ["r" * 301],
                    "few_shot_examples": ["e" * 301],
                },
                deps=deps,
            )
            assert created["ok"] is False
            assert created["error"] in {"invalid_name", "invalid_summary", "invalid_style_rules", "invalid_few_shot_examples"}

    def test_student_persona_read_json_logs_warning_on_parse_error(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            bad = root / "data" / "student_profiles" / "S001.json"
            bad.parent.mkdir(parents=True, exist_ok=True)
            bad.write_text("{bad json", encoding="utf-8")
            with self.assertLogs("services.api.student_persona_api_service", level=logging.WARNING) as logs:
                result = student_personas_get_api("S001", deps=deps)
            assert result["ok"] is True
            assert "failed to read/parse json file" in "\n".join(logs.output)


if __name__ == "__main__":
    unittest.main()
