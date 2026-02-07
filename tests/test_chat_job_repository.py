import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.chat_job_repository import (
    ChatJobRepositoryDeps,
    chat_job_exists,
    chat_job_path,
    load_chat_job,
    write_chat_job,
)


def _atomic_write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ChatJobRepositoryTest(unittest.TestCase):
    def test_chat_job_path_sanitizes_identifier(self):
        with TemporaryDirectory() as td:
            deps = ChatJobRepositoryDeps(
                chat_job_dir=Path(td),
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-01-01T00:00:00",
            )
            path = chat_job_path("cjob:abc/12", deps)
            self.assertEqual(path.name, "cjob_abc_12")

    def test_load_chat_job_missing_raises(self):
        with TemporaryDirectory() as td:
            deps = ChatJobRepositoryDeps(
                chat_job_dir=Path(td),
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-01-01T00:00:00",
            )
            with self.assertRaises(FileNotFoundError):
                load_chat_job("missing_job", deps)

    def test_write_chat_job_merges_and_overwrites(self):
        with TemporaryDirectory() as td:
            deps = ChatJobRepositoryDeps(
                chat_job_dir=Path(td),
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-01-01T00:00:00",
            )
            first = write_chat_job("job_1", {"status": "queued", "progress": 1}, deps, overwrite=True)
            self.assertEqual(first["status"], "queued")
            self.assertEqual(first["progress"], 1)
            self.assertEqual(first["updated_at"], "2026-01-01T00:00:00")

            merged = write_chat_job("job_1", {"progress": 2}, deps, overwrite=False)
            self.assertEqual(merged["status"], "queued")
            self.assertEqual(merged["progress"], 2)

            replaced = write_chat_job("job_1", {"status": "done"}, deps, overwrite=True)
            self.assertEqual(replaced["status"], "done")
            self.assertNotIn("progress", replaced)

    def test_chat_job_exists_checks_job_json(self):
        with TemporaryDirectory() as td:
            deps = ChatJobRepositoryDeps(
                chat_job_dir=Path(td),
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-01-01T00:00:00",
            )
            self.assertFalse(chat_job_exists("job_x", deps))
            write_chat_job("job_x", {"status": "queued"}, deps, overwrite=True)
            self.assertTrue(chat_job_exists("job_x", deps))


if __name__ == "__main__":
    unittest.main()
