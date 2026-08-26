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
            escaped = chat_job_path("..", deps)
            self.assertEqual(escaped.parent, Path(td))
            self.assertTrue(escaped.name.startswith("job_"))

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

            replaced = write_chat_job("job_1", {"status": "queued", "note": "fresh"}, deps, overwrite=True)
            self.assertEqual(replaced["status"], "queued")
            self.assertEqual(replaced["note"], "fresh")
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

    def test_write_chat_job_rejects_done_to_queued(self):
        with TemporaryDirectory() as td:
            deps = ChatJobRepositoryDeps(
                chat_job_dir=Path(td),
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-01-01T00:00:00",
            )
            job_dir = chat_job_path("job_done", deps)
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps({"status": "done", "reply": "ok"}, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as ctx:
                write_chat_job("job_done", {"status": "queued"}, deps, overwrite=False)
            self.assertIn("invalid_chat_job_transition:done->queued", str(ctx.exception))

            persisted = load_chat_job("job_done", deps)
            self.assertEqual(persisted["status"], "done")
            self.assertEqual(persisted["reply"], "ok")
            self.assertNotIn("updated_at", persisted)

            with self.assertRaises(ValueError) as overwrite_ctx:
                write_chat_job("job_done", {"status": "queued", "reply": "rewound"}, deps, overwrite=True)
            self.assertIn("invalid_chat_job_transition:done->queued", str(overwrite_ctx.exception))
            self.assertEqual(load_chat_job("job_done", deps)["reply"], "ok")

    def test_write_chat_job_queued_to_failed_is_allowed(self):
        with TemporaryDirectory() as td:
            deps = ChatJobRepositoryDeps(
                chat_job_dir=Path(td),
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-01-01T00:00:00",
            )
            write_chat_job("job_fail", {"status": "queued"}, deps, overwrite=True)
            failed = write_chat_job(
                "job_fail",
                {"status": "failed", "error": "history_prewrite_failed"},
                deps,
                overwrite=False,
            )
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["error"], "history_prewrite_failed")
            self.assertEqual(load_chat_job("job_fail", deps)["status"], "failed")

    def test_write_chat_job_non_status_update_on_done_is_allowed(self):
        with TemporaryDirectory() as td:
            deps = ChatJobRepositoryDeps(
                chat_job_dir=Path(td),
                atomic_write_json=_atomic_write_json,
                now_iso=lambda: "2026-01-01T00:00:00",
            )
            job_dir = chat_job_path("job_done", deps)
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps({"status": "done", "reply": "ok"}, ensure_ascii=False),
                encoding="utf-8",
            )
            merged = write_chat_job("job_done", {"note": "meta"}, deps, overwrite=False)
            self.assertEqual(merged["status"], "done")
            self.assertEqual(merged["note"], "meta")
            self.assertEqual(merged["reply"], "ok")


if __name__ == "__main__":
    unittest.main()
