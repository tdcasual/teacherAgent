import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.chat_idempotency_service import (
    ChatIdempotencyDeps,
    get_chat_job_id_by_request,
    request_map_get,
    request_map_set_if_absent,
    upsert_chat_request_index,
)


def _safe_fs_id(value: str, prefix: str = "id") -> str:
    text = str(value or "").strip().replace("/", "_").replace(" ", "_")
    if not text:
        return f"{prefix}_empty"
    return text


class ChatIdempotencyServiceTest(unittest.TestCase):
    def test_request_map_set_if_absent_is_atomic(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = ChatIdempotencyDeps(
                request_map_dir=root / "request_map",
                safe_fs_id=_safe_fs_id,
                chat_job_exists=lambda _job_id: True,
            )
            self.assertTrue(request_map_set_if_absent("req_1", "job_1", deps))
            self.assertFalse(request_map_set_if_absent("req_1", "job_2", deps))

    def test_request_map_get_cleans_stale_entry(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = ChatIdempotencyDeps(
                request_map_dir=root / "request_map",
                safe_fs_id=_safe_fs_id,
                chat_job_exists=lambda _job_id: False,
            )
            deps.request_map_dir.mkdir(parents=True, exist_ok=True)
            stale_path = deps.request_map_dir / "req_2.txt"
            stale_path.write_text("job_missing", encoding="utf-8")
            self.assertIsNone(request_map_get("req_2", deps))
            self.assertFalse(stale_path.exists())

    def test_get_chat_job_id_by_request_uses_request_map_only(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = ChatIdempotencyDeps(
                request_map_dir=root / "request_map",
                safe_fs_id=_safe_fs_id,
                chat_job_exists=lambda job_id: job_id == "job_legacy",
            )
            upsert_chat_request_index("req_legacy", "job_legacy", deps)
            self.assertEqual(get_chat_job_id_by_request("req_legacy", deps), "job_legacy")
            self.assertIsNone(get_chat_job_id_by_request("req_unknown", deps))


if __name__ == "__main__":
    unittest.main()
