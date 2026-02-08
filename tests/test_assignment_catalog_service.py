import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_catalog_service import (
    AssignmentCatalogDeps,
    AssignmentMetaPostprocessDeps,
    build_assignment_detail,
    find_assignment_for_date,
    list_assignments,
    postprocess_assignment_meta,
)


class AssignmentCatalogServiceTest(unittest.TestCase):
    def _catalog_deps(self, root: Path):
        return AssignmentCatalogDeps(
            data_dir=root / "data",
            app_root=root,
            load_assignment_meta=lambda folder: json.loads((folder / "meta.json").read_text(encoding="utf-8")),
            load_assignment_requirements=lambda folder: json.loads((folder / "requirements.json").read_text(encoding="utf-8"))
            if (folder / "requirements.json").exists()
            else {},
            count_csv_rows=lambda path: max(0, len(path.read_text(encoding="utf-8").splitlines()) - 1),
            sanitize_filename=lambda name: str(name or "").strip(),
        )

    def test_find_assignment_for_date_prefers_teacher_and_specific(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            assignments_dir = root / "data" / "assignments"
            auto_dir = assignments_dir / "AUTO_S1_2026-02-08"
            teacher_dir = assignments_dir / "HW_2026-02-08"
            auto_dir.mkdir(parents=True, exist_ok=True)
            teacher_dir.mkdir(parents=True, exist_ok=True)

            (auto_dir / "meta.json").write_text(
                json.dumps({"assignment_id": "AUTO_S1_2026-02-08", "source": "auto", "scope": "public"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (teacher_dir / "meta.json").write_text(
                json.dumps(
                    {
                        "assignment_id": "HW_2026-02-08",
                        "date": "2026-02-08",
                        "source": "teacher",
                        "scope": "student",
                        "student_ids": ["S1"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            found = find_assignment_for_date(
                date_str="2026-02-08",
                student_id="S1",
                class_name="高二2403班",
                deps=self._catalog_deps(root),
            )

            self.assertIsNotNone(found)
            self.assertEqual(found["meta"].get("assignment_id"), "HW_2026-02-08")

    def test_build_assignment_detail_includes_delivery_and_stem_text(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "data" / "assignments" / "HW_1"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "meta.json").write_text(
                json.dumps(
                    {
                        "assignment_id": "HW_1",
                        "date": "2026-02-08",
                        "delivery_mode": "pdf",
                        "source_files": ["paper 1.pdf"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (folder / "requirements.json").write_text(
                json.dumps({"core_concepts": ["牛顿定律"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            stem_path = root / "tmp" / "stem_q1.txt"
            stem_path.parent.mkdir(parents=True, exist_ok=True)
            stem_path.write_text("题干文本", encoding="utf-8")
            (folder / "questions.csv").write_text("question_id,stem_ref\nQ1,tmp/stem_q1.txt\n", encoding="utf-8")

            detail = build_assignment_detail(folder=folder, include_text=True, deps=self._catalog_deps(root))

            self.assertEqual(detail.get("question_count"), 1)
            self.assertEqual(detail["questions"][0].get("stem_text"), "题干文本")
            self.assertEqual(detail.get("delivery")["files"][0].get("url"), "/assignment/HW_1/download?file=paper%201.pdf")

    def test_postprocess_assignment_meta_writes_scope_and_expected_students(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "data" / "assignments" / "HW_1"
            folder.mkdir(parents=True, exist_ok=True)
            meta_path = folder / "meta.json"
            meta_path.write_text(
                json.dumps({"assignment_id": "HW_1", "scope": "class", "class_name": "高二2403班"}, ensure_ascii=False),
                encoding="utf-8",
            )

            def _load_profile_file(path: Path):
                return json.loads(path.read_text(encoding="utf-8"))

            def _atomic_write_json(path: Path, payload):
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            deps = AssignmentMetaPostprocessDeps(
                data_dir=root / "data",
                discussion_complete_marker="[DISCUSS_OK]",
                load_profile_file=_load_profile_file,
                parse_ids_value=lambda value: [str(x).strip() for x in (value if isinstance(value, list) else []) if str(x).strip()],
                resolve_scope=lambda scope, _student_ids, class_name: "class" if scope == "class" and class_name else "public",
                normalize_due_at=lambda value: str(value or "").strip(),
                compute_expected_students=lambda scope, class_name, _student_ids: ["S1", "S2"] if scope == "class" and class_name else [],
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-02-08T12:00:00",
            )

            postprocess_assignment_meta(
                assignment_id="HW_1",
                due_at="2026-02-09T20:00:00",
                expected_students=None,
                completion_policy=None,
                deps=deps,
            )

            updated = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(updated.get("due_at"), "2026-02-09T20:00:00")
            self.assertEqual(updated.get("expected_students"), ["S1", "S2"])
            self.assertEqual(updated.get("completion_policy", {}).get("discussion_marker"), "[DISCUSS_OK]")

    def test_postprocess_assignment_meta_ignores_invalid_assignment_id_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            def _load_profile_file(path: Path):
                return json.loads(path.read_text(encoding="utf-8"))

            def _atomic_write_json(path: Path, payload):
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            deps = AssignmentMetaPostprocessDeps(
                data_dir=root / "data",
                discussion_complete_marker="[DISCUSS_OK]",
                load_profile_file=_load_profile_file,
                parse_ids_value=lambda value: [str(x).strip() for x in (value if isinstance(value, list) else []) if str(x).strip()],
                resolve_scope=lambda scope, _student_ids, class_name: "class" if scope == "class" and class_name else "public",
                normalize_due_at=lambda value: str(value or "").strip(),
                compute_expected_students=lambda scope, class_name, _student_ids: ["S1", "S2"] if scope == "class" and class_name else [],
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-02-08T12:00:00",
            )

            postprocess_assignment_meta(
                assignment_id="../escape",
                due_at="2026-02-09T20:00:00",
                expected_students=None,
                completion_policy=None,
                deps=deps,
            )
            self.assertFalse((root / "data" / "outside" / "meta.json").exists())


if __name__ == "__main__":
    unittest.main()
