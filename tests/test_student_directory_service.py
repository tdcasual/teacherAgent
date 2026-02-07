import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.student_directory_service import (
    StudentDirectoryDeps,
    list_all_student_ids,
    list_student_ids_by_class,
    student_candidates_by_name,
    student_search,
)


def _normalize(text: str) -> str:
    import re

    return re.sub(r"\s+", "", text or "").lower()


class StudentDirectoryServiceTest(unittest.TestCase):
    def _deps(self, root: Path):
        return StudentDirectoryDeps(
            data_dir=root / "data",
            load_profile_file=lambda path: json.loads(path.read_text(encoding="utf-8")),
            normalize=_normalize,
        )

    def _write_profile(self, root: Path, student_id: str, student_name: str, class_name: str, aliases=None):
        path = root / "data" / "student_profiles" / f"{student_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "student_id": student_id,
                    "student_name": student_name,
                    "class_name": class_name,
                    "aliases": aliases or [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_student_search_returns_ranked_matches(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_profile(root, "S1", "张三", "高二2403班", aliases=["小张"])
            self._write_profile(root, "S2", "李四", "高二2404班", aliases=["老李"])

            result = student_search("张", 5, self._deps(root))

            matches = result.get("matches") or []
            self.assertTrue(matches)
            self.assertEqual(matches[0].get("student_id"), "S1")

    def test_candidates_match_alias_and_exact(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_profile(root, "S1", "张三", "高二2403班", aliases=["阿三"])

            by_alias = student_candidates_by_name("阿三", self._deps(root))
            by_exact = student_candidates_by_name("高二2403班张三", self._deps(root))

            self.assertEqual(len(by_alias), 1)
            self.assertEqual(by_alias[0].get("student_id"), "S1")
            self.assertEqual(len(by_exact), 1)
            self.assertEqual(by_exact[0].get("student_id"), "S1")

    def test_list_ids_by_class_filters_and_sorts(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_profile(root, "S2", "李四", "高二2403班")
            self._write_profile(root, "S1", "张三", "高二2403班")
            self._write_profile(root, "S3", "王五", "高二2404班")

            ids_all = list_all_student_ids(self._deps(root))
            ids_class = list_student_ids_by_class("高二2403班", self._deps(root))

            self.assertEqual(ids_all, ["S1", "S2", "S3"])
            self.assertEqual(ids_class, ["S1", "S2"])


if __name__ == "__main__":
    unittest.main()
