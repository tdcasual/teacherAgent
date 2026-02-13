import importlib
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


class ChatAttachmentFlowTest(unittest.TestCase):
    def test_upload_markdown_and_attach_to_chat_start(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            with TestClient(app_mod.app) as client:
                upload_res = client.post(
                    "/chat/attachments",
                    data={
                        "role": "teacher",
                        "teacher_id": "t-001",
                        "session_id": "main",
                        "request_id": "req_attach_001",
                    },
                    files=[("files", ("notes.md", "# 复习\n牛顿第二定律 F=ma".encode("utf-8"), "text/markdown"))],
                )
                self.assertEqual(upload_res.status_code, 200)
                payload = upload_res.json() or {}
                attachments = payload.get("attachments") or []
                self.assertEqual(len(attachments), 1)
                attachment_id = str(attachments[0].get("attachment_id") or "")
                self.assertTrue(attachment_id)
                self.assertEqual(attachments[0].get("status"), "ready")

                status_res = client.get(
                    "/chat/attachments/status",
                    params=[
                        ("role", "teacher"),
                        ("teacher_id", "t-001"),
                        ("session_id", "main"),
                        ("attachment_ids", attachment_id),
                    ],
                )
                self.assertEqual(status_res.status_code, 200)
                status_payload = status_res.json() or {}
                status_items = status_payload.get("attachments") or []
                self.assertEqual(len(status_items), 1)
                self.assertEqual(status_items[0].get("status"), "ready")

                chat_res = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_chat_with_attachment_001",
                        "role": "teacher",
                        "teacher_id": "t-001",
                        "session_id": "main",
                        "messages": [{"role": "user", "content": "请用附件做总结"}],
                        "attachments": [{"attachment_id": attachment_id}],
                    },
                )
                self.assertEqual(chat_res.status_code, 200)
                job_id = (chat_res.json() or {}).get("job_id")
                self.assertTrue(job_id)

                job = app_mod.load_chat_job(job_id)
                req_payload = (job or {}).get("request") or {}
                self.assertEqual((req_payload.get("messages") or [{}])[-1].get("content"), "请用附件做总结")
                attachment_context = str(req_payload.get("attachment_context") or "")
                self.assertIn("F=ma", attachment_context)

    def test_rejects_too_many_files(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            with TestClient(app_mod.app) as client:
                files = [
                    ("files", (f"f{i}.md", b"x", "text/markdown"))
                    for i in range(6)
                ]
                res = client.post(
                    "/chat/attachments",
                    data={
                        "role": "teacher",
                        "teacher_id": "t-001",
                        "session_id": "main",
                        "request_id": "req_attach_limit_001",
                    },
                    files=files,
                )
                self.assertEqual(res.status_code, 400)
                detail = (res.json() or {}).get("detail")
                self.assertIn("最多上传", str(detail))


if __name__ == "__main__":
    unittest.main()
