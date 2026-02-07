from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.lesson_core_tool_service import LessonCaptureDeps, lesson_capture


class LessonCoreToolServiceTest(unittest.TestCase):
    def test_lesson_capture_validates_required_fields(self):
        deps = LessonCaptureDeps(
            is_safe_tool_id=lambda value: bool(str(value or "").strip()),
            resolve_app_path=lambda value, must_exist=True: Path("/tmp") / str(value),
            app_root=Path("/tmp/app"),
            run_script=lambda cmd: "ok",
        )
        self.assertEqual(lesson_capture({}, deps=deps).get("error"), "invalid_lesson_id")
        self.assertEqual(
            lesson_capture({"lesson_id": "L1", "sources": ["a.md"]}, deps=deps).get("error"),
            "missing_topic",
        )

    def test_lesson_capture_rejects_outside_sources(self):
        deps = LessonCaptureDeps(
            is_safe_tool_id=lambda value: True,
            resolve_app_path=lambda value, must_exist=True: None,
            app_root=Path("/tmp/app"),
            run_script=lambda cmd: "ok",
        )
        result = lesson_capture({"lesson_id": "L1", "topic": "T", "sources": ["/etc/passwd"]}, deps=deps)
        self.assertEqual(result.get("error"), "source_not_found_or_outside_app_root")

    def test_lesson_capture_success_builds_command(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            src = root / "source.md"
            src.write_text("content", encoding="utf-8")
            output_dir = root / "out"
            captured = {}

            def resolve_app_path(value, must_exist=True):  # type: ignore[no-untyped-def]
                path = Path(value)
                if must_exist and not path.exists():
                    return None
                return path

            deps = LessonCaptureDeps(
                is_safe_tool_id=lambda value: True,
                resolve_app_path=resolve_app_path,
                app_root=root,
                run_script=lambda cmd: captured.setdefault("cmd", cmd) or "ok",
            )

            result = lesson_capture(
                {
                    "lesson_id": "L1",
                    "topic": "动量守恒",
                    "sources": [str(src)],
                    "out_base": str(output_dir),
                    "force_ocr": True,
                },
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            cmd = captured.get("cmd") or []
            self.assertIn("--lesson-id", cmd)
            self.assertIn("L1", cmd)
            self.assertIn("--force-ocr", cmd)
            self.assertIn("--out-base", cmd)


if __name__ == "__main__":
    unittest.main()
