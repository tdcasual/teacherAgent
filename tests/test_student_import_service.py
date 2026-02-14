import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.student_import_service import (
    StudentImportDeps,
    import_students_from_responses,
    resolve_responses_file,
    student_import,
)


def _load_profile_file(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "student_name", "class_name", "exam_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class StudentImportServiceTest(unittest.TestCase):
    def test_resolve_responses_file_supports_relative_file_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "app"
            data_dir = root / "data"
            target = app_root / "exports" / "responses.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("student_id,student_name,class_name,exam_id\n", encoding="utf-8")
            deps = StudentImportDeps(
                app_root=app_root,
                data_dir=data_dir,
                load_profile_file=_load_profile_file,
                now_iso=lambda: "2026-02-07T10:00:00",
            )

            resolved = resolve_responses_file(None, "exports/responses.csv", deps=deps)
            self.assertEqual(resolved, target.resolve())

    def test_resolve_responses_file_reads_manifest_responses_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "app"
            data_dir = root / "data"
            manifest_path = data_dir / "exams" / "EX1" / "manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps({"files": {"responses": "data/staging/latest_responses.csv"}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            target = app_root / "data" / "staging" / "latest_responses.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("student_id,student_name,class_name,exam_id\n", encoding="utf-8")
            deps = StudentImportDeps(
                app_root=app_root,
                data_dir=data_dir,
                load_profile_file=_load_profile_file,
                now_iso=lambda: "2026-02-07T10:00:00",
            )

            resolved = resolve_responses_file("EX1", None, deps=deps)
            self.assertEqual(resolved, target.resolve())

    def test_resolve_responses_file_rejects_invalid_exam_id_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = StudentImportDeps(
                app_root=root / "app",
                data_dir=root / "data",
                load_profile_file=_load_profile_file,
                now_iso=lambda: "2026-02-07T10:00:00",
            )
            resolved = resolve_responses_file("../escape", None, deps=deps)
            self.assertIsNone(resolved)

    def test_resolve_responses_file_rejects_absolute_path_outside_allowed_roots(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "app"
            data_dir = root / "data"
            outside = root / "outside.csv"
            outside.write_text("student_id,student_name,class_name,exam_id\n", encoding="utf-8")
            deps = StudentImportDeps(
                app_root=app_root,
                data_dir=data_dir,
                load_profile_file=_load_profile_file,
                now_iso=lambda: "2026-02-07T10:00:00",
            )

            resolved = resolve_responses_file(None, str(outside), deps=deps)
            self.assertIsNone(resolved)

    def test_resolve_responses_file_manifest_rejects_outside_absolute_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "app"
            data_dir = root / "data"
            outside = root / "outside.csv"
            outside.write_text("student_id,student_name,class_name,exam_id\n", encoding="utf-8")
            manifest_path = data_dir / "exams" / "EX1" / "manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps({"files": {"responses": str(outside)}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            deps = StudentImportDeps(
                app_root=app_root,
                data_dir=data_dir,
                load_profile_file=_load_profile_file,
                now_iso=lambda: "2026-02-07T10:00:00",
            )

            resolved = resolve_responses_file("EX1", None, deps=deps)
            self.assertIsNone(resolved)

    def test_import_students_from_responses_creates_and_updates_aliases(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = StudentImportDeps(
                app_root=root / "app",
                data_dir=root / "data",
                load_profile_file=_load_profile_file,
                now_iso=lambda: "2026-02-07T10:00:00",
            )
            source_a = root / "inputs" / "a.csv"
            _write_csv(
                source_a,
                [
                    {"student_id": "", "student_name": "Alice", "class_name": "C1", "exam_id": "EX1"},
                    {"student_id": "S1", "student_name": "Bob", "class_name": "C2", "exam_id": "EX1"},
                ],
            )
            result_a = import_students_from_responses(source_a, deps=deps, mode="merge")
            self.assertTrue(result_a.get("ok"))
            self.assertEqual(result_a.get("created"), 2)
            self.assertEqual(result_a.get("updated"), 0)

            source_b = root / "inputs" / "b.csv"
            _write_csv(
                source_b,
                [
                    {"student_id": "S1", "student_name": "Robert", "class_name": "C2", "exam_id": "EX2"},
                ],
            )
            result_b = import_students_from_responses(source_b, deps=deps, mode="merge")
            self.assertTrue(result_b.get("ok"))
            self.assertEqual(result_b.get("created"), 0)
            self.assertEqual(result_b.get("updated"), 1)

            profile_s1 = _load_profile_file(root / "data" / "student_profiles" / "S1.json")
            self.assertEqual(profile_s1.get("student_name"), "Bob")
            self.assertIn("Robert", profile_s1.get("aliases") or [])
            self.assertTrue(profile_s1.get("import_history"))

    def test_student_import_rejects_unsupported_source(self):
        deps = StudentImportDeps(
            app_root=Path("/tmp/app"),
            data_dir=Path("/tmp/data"),
            load_profile_file=_load_profile_file,
            now_iso=lambda: "2026-02-07T10:00:00",
        )
        result = student_import({"source": "unknown"}, deps=deps)
        self.assertEqual(result.get("error"), "unsupported source: unknown")

    def test_import_skips_invalid_student_id_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = StudentImportDeps(
                app_root=root / "app",
                data_dir=root / "data",
                load_profile_file=_load_profile_file,
                now_iso=lambda: "2026-02-07T10:00:00",
            )
            source = root / "inputs" / "evil.csv"
            _write_csv(
                source,
                [
                    {"student_id": "../escape", "student_name": "Evil", "class_name": "C1", "exam_id": "EX1"},
                    {"student_id": "S1", "student_name": "Bob", "class_name": "C2", "exam_id": "EX1"},
                ],
            )
            result = import_students_from_responses(source, deps=deps, mode="merge")
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("created"), 1)
            self.assertEqual(result.get("skipped"), 1)
            self.assertTrue((root / "data" / "student_profiles" / "S1.json").exists())
            self.assertFalse((root / "data" / "escape.json").exists())


if __name__ == "__main__":
    unittest.main()
