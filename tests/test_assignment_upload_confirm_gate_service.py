import unittest

from services.api.assignment_upload_confirm_gate_service import (
    AssignmentUploadConfirmGateError,
    ensure_assignment_upload_confirm_ready,
)


class AssignmentUploadConfirmGateServiceTest(unittest.TestCase):
    def test_confirmed_returns_idempotent_payload(self):
        payload = ensure_assignment_upload_confirm_ready({"status": "confirmed", "assignment_id": "HW_1"})
        self.assertEqual(payload.get("ok"), True)
        self.assertEqual(payload.get("status"), "confirmed")
        self.assertEqual(payload.get("assignment_id"), "HW_1")
        self.assertEqual(payload.get("message"), "作业已发布（已确认）。")

    def test_not_done_raises_job_not_ready_detail(self):
        with self.assertRaises(AssignmentUploadConfirmGateError) as cm:
            ensure_assignment_upload_confirm_ready({"status": "processing", "step": "ocr", "progress": 40})
        self.assertEqual(cm.exception.status_code, 400)
        detail = cm.exception.detail
        self.assertEqual(detail.get("error"), "job_not_ready")
        self.assertEqual(detail.get("status"), "processing")
        self.assertEqual(detail.get("step"), "ocr")
        self.assertEqual(detail.get("progress"), 40)
        self.assertEqual(detail.get("message"), "解析尚未完成，请稍后再发布草稿。")

    def test_done_returns_none(self):
        payload = ensure_assignment_upload_confirm_ready({"status": "done", "assignment_id": "HW_2"})
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
