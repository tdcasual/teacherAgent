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
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class UploadJobNotReadyErrorsTest(unittest.TestCase):
    def test_confirm_not_ready_returns_detail_object(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            client = TestClient(app_mod.app)

            job_id = "job_nr_001"
            job_dir = Path(os.environ["UPLOADS_DIR"]) / "assignment_jobs" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "assignment_id": "HW_NR_2026-02-05",
                        "status": "processing",
                        "step": "ocr",
                        "progress": 35,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            res = client.post("/assignment/upload/confirm", json={"job_id": job_id, "strict_requirements": True})
            self.assertEqual(res.status_code, 400)
            detail = res.json()["detail"]
            self.assertEqual(detail["error"], "job_not_ready")
            self.assertIn("解析尚未完成", detail["message"])
            self.assertEqual(detail["status"], "processing")
            self.assertEqual(detail["step"], "ocr")
            self.assertEqual(detail["progress"], 35)

    def test_draft_not_ready_returns_detail_object(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            client = TestClient(app_mod.app)

            job_id = "job_nr_002"
            job_dir = Path(os.environ["UPLOADS_DIR"]) / "assignment_jobs" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "assignment_id": "HW_NR2_2026-02-05",
                        "status": "queued",
                        "step": "queued",
                        "progress": 0,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            res = client.get("/assignment/upload/draft", params={"job_id": job_id})
            self.assertEqual(res.status_code, 400)
            detail = res.json()["detail"]
            self.assertEqual(detail["error"], "job_not_ready")
            self.assertEqual(detail["status"], "queued")

            res = client.post("/assignment/upload/draft/save", json={"job_id": job_id, "requirements": {}, "questions": []})
            self.assertEqual(res.status_code, 400)
            detail = res.json()["detail"]
            self.assertEqual(detail["error"], "job_not_ready")


if __name__ == "__main__":
    unittest.main()
