import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_catalog_service import ExamCatalogDeps, list_exams


class ExamCatalogServiceTest(unittest.TestCase):
    def test_list_exams_reads_manifest_and_sorts_desc(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            d = root / "exams"
            (d / "E1").mkdir(parents=True)
            (d / "E2").mkdir(parents=True)

            (d / "E1" / "manifest.json").write_text(
                json.dumps({"exam_id": "EX1", "generated_at": "2026-02-06T09:00:00", "counts": {"students": 10, "responses": 120}}),
                encoding="utf-8",
            )
            (d / "E2" / "manifest.json").write_text(
                json.dumps({"exam_id": "EX2", "generated_at": "2026-02-07T09:00:00", "counts": {"students": 12, "responses": 140}}),
                encoding="utf-8",
            )

            deps = ExamCatalogDeps(data_dir=root, load_profile_file=lambda p: json.loads(p.read_text(encoding="utf-8")))
            out = list_exams(deps=deps)
            exams = out.get("exams") or []
            self.assertEqual(exams[0].get("exam_id"), "EX2")
            self.assertEqual(exams[1].get("students"), 10)

    def test_list_exams_supports_pagination_and_limit_cap(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            d = root / "exams"
            d.mkdir(parents=True, exist_ok=True)
            for i in range(1, 6):
                folder = d / f"E{i}"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "manifest.json").write_text(
                    json.dumps(
                        {
                            "exam_id": f"EX{i}",
                            "generated_at": f"2026-02-0{i}T09:00:00",
                            "counts": {"students": i, "responses": i * 10},
                        }
                    ),
                    encoding="utf-8",
                )

            deps = ExamCatalogDeps(data_dir=root, load_profile_file=lambda p: json.loads(p.read_text(encoding="utf-8")))
            page = list_exams(limit=2, cursor=1, deps=deps)
            self.assertEqual(page.get("total"), 5)
            self.assertEqual(page.get("limit"), 2)
            self.assertEqual(page.get("cursor"), 1)
            self.assertTrue(page.get("has_more"))
            self.assertEqual(len(page.get("exams") or []), 2)

            capped = list_exams(limit=9999, cursor=0, deps=deps)
            self.assertEqual(capped.get("limit"), 100)


if __name__ == "__main__":
    unittest.main()
