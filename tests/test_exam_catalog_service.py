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


if __name__ == "__main__":
    unittest.main()
