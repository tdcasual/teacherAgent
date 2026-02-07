import importlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    # Ensure any previously imported module picks up new env paths
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def make_valid_requirements():
    return {
        "subject": "物理",
        "topic": "欧姆表原理",
        "grade_level": "高二",
        "class_level": "中等",
        "core_concepts": ["电动势E", "内阻r", "欧姆调零"],
        "typical_problem": "欧姆挡内部电路分析与读数",
        "misconceptions": ["调零本质理解错误", "换挡不重新调零", "刻度不均匀原因不清", "电池老化误差判断错"],
        "duration_minutes": 40,
        "preferences": ["B提升"],
        "extra_constraints": "允许画图",
    }


class UploadDraftFlowTest(unittest.TestCase):
    def test_upload_draft_get_save_confirm_flow(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            self.assertTrue(hasattr(app_mod, "_assignment_api_deps"))
            client = TestClient(app_mod.app)

            job_id = "job_test_001"
            assignment_id = "HW_TEST_2026-02-05"
            job_dir = Path(os.environ["UPLOADS_DIR"]) / "assignment_jobs" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)

            job = {
                "job_id": job_id,
                "assignment_id": assignment_id,
                "date": "2026-02-05",
                "scope": "public",
                "class_name": "高二2403班",
                "student_ids": [],
                "source_files": ["paper.pdf"],
                "answer_files": ["ans.pdf"],
                "delivery_mode": "pdf",
                "status": "done",
            }
            (job_dir / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

            parsed = {
                "questions": [
                    {
                        "stem": "已知电动势E、内阻r，求电流表达式。",
                        "answer": "I=E/(r+R)",
                        "kp": "欧姆定律",
                        "difficulty": "basic",
                        "score": 5,
                        "tags": ["公式"],
                        "type": "calc",
                    }
                ],
                "requirements": {
                    "subject": "物理",
                    "topic": "",
                    "grade_level": "",
                    "class_level": "",
                    "core_concepts": [],
                    "typical_problem": "",
                    "misconceptions": [],
                    "duration_minutes": 0,
                    "preferences": [],
                    "extra_constraints": "",
                },
                "missing": [],
                "warnings": [],
                "delivery_mode": "pdf",
                "question_count": 1,
                "autofilled": False,
            }
            (job_dir / "parsed.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

            # Draft should be accessible and include full question list
            res = client.get("/assignment/upload/draft", params={"job_id": job_id})
            self.assertEqual(res.status_code, 200)
            draft = res.json()["draft"]
            self.assertEqual(draft["assignment_id"], assignment_id)
            self.assertEqual(len(draft["questions"]), 1)
            self.assertIn("requirements_missing", draft)

            # Strict confirm should fail when requirements missing
            res = client.post("/assignment/upload/confirm", json={"job_id": job_id, "strict_requirements": True})
            self.assertEqual(res.status_code, 400)
            detail = res.json()["detail"]
            self.assertEqual(detail["error"], "requirements_missing")

            # Save a complete draft (requirements + updated answer)
            complete_req = make_valid_requirements()
            questions = draft["questions"]
            questions[0]["answer"] = "I=\\frac{E}{r+R}"
            res = client.post(
                "/assignment/upload/draft/save",
                json={"job_id": job_id, "requirements": complete_req, "questions": questions},
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["requirements_missing"], [])

            # Confirm should now succeed and create assignment meta
            res = client.post("/assignment/upload/confirm", json={"job_id": job_id, "strict_requirements": True})
            self.assertEqual(res.status_code, 200)
            payload = res.json()
            self.assertEqual(payload["assignment_id"], assignment_id)
            meta_path = Path(os.environ["DATA_DIR"]) / "assignments" / assignment_id / "meta.json"
            self.assertTrue(meta_path.exists())

    def test_teacher_edits_override_invalid_parsed_values(self):
        """Regression: teacher edits must overwrite invalid/non-normalized parsed values."""
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            client = TestClient(app_mod.app)

            job_id = "job_test_002"
            assignment_id = "HW_TEST2_2026-02-05"
            job_dir = Path(os.environ["UPLOADS_DIR"]) / "assignment_jobs" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)

            job = {
                "job_id": job_id,
                "assignment_id": assignment_id,
                "date": "2026-02-05",
                "scope": "public",
                "class_name": "高二2403班",
                "student_ids": [],
                "source_files": [],
                "answer_files": [],
                "delivery_mode": "image",
                "status": "done",
            }
            (job_dir / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

            # Parsed requirements contain invalid values that are truthy and would previously block overwrites.
            parsed = {
                "questions": [{"stem": "test", "answer": "", "kp": "", "difficulty": "basic", "score": 5, "type": ""}],
                "requirements": {
                    "subject": "物理",
                    "topic": "静电场",
                    "grade_level": "高二",
                    "class_level": "普通",  # invalid (not in allowed)
                    "core_concepts": ["电场", "电势", "电势能"],
                    "typical_problem": "综合应用",
                    "misconceptions": ["只有一条"],  # < 4
                    "duration_minutes": 30,  # invalid but truthy
                    "preferences": ["B提升"],
                    "extra_constraints": "",
                },
                "missing": [],
                "warnings": [],
                "delivery_mode": "image",
                "question_count": 1,
                "autofilled": False,
            }
            (job_dir / "parsed.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

            complete_req = make_valid_requirements()
            res = client.post(
                "/assignment/upload/draft/save",
                json={"job_id": job_id, "requirements": complete_req, "questions": parsed["questions"]},
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["requirements_missing"], [])

            res = client.post("/assignment/upload/confirm", json={"job_id": job_id, "strict_requirements": True})
            self.assertEqual(res.status_code, 200)
            meta_path = Path(os.environ["DATA_DIR"]) / "assignments" / assignment_id / "meta.json"
            self.assertTrue(meta_path.exists())


if __name__ == "__main__":
    unittest.main()
