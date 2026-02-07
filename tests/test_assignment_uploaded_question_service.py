import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_uploaded_question_service import (
    AssignmentUploadedQuestionDeps,
    write_uploaded_questions,
)


class AssignmentUploadedQuestionServiceTest(unittest.TestCase):
    def test_writes_markdown_and_csv_rows(self):
        with TemporaryDirectory() as td:
            out_dir = Path(td)
            deps = AssignmentUploadedQuestionDeps(
                safe_slug=lambda value: str(value).replace("-", "_") or "A",
                normalize_difficulty=lambda value: str(value or "basic"),
            )

            rows = write_uploaded_questions(
                out_dir,
                "HW-1",
                [
                    {
                        "stem": "请计算加速度",
                        "answer": "a=F/m",
                        "kp": "牛顿定律",
                        "difficulty": "medium",
                        "tags": ["力学", "上传"],
                    }
                ],
                deps=deps,
            )

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertTrue((out_dir / "questions.csv").exists())
            self.assertTrue(Path(row["stem_ref"]).exists())
            self.assertTrue(Path(row["answer_ref"]).exists())

            with (out_dir / "questions.csv").open(encoding="utf-8") as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 1)
            self.assertEqual(csv_rows[0]["kp_id"], "牛顿定律")


if __name__ == "__main__":
    unittest.main()
