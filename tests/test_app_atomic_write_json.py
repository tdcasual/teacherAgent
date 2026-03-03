import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.api.job_repository import _atomic_write_json
from services.api.teacher_session_compaction_helpers import write_teacher_session_records


class AppAtomicWriteJsonTest(unittest.TestCase):
    def test_atomic_write_json_handles_concurrent_writers(self):
        with TemporaryDirectory() as td:
            target = Path(td) / "uploads" / "chat_jobs" / "cjob_concurrent" / "job.json"
            barrier = threading.Barrier(2)
            errors = []

            original_replace = Path.replace

            def patched_replace(self: Path, other):
                if self.parent == target.parent and self.name.startswith("job.json") and self.name.endswith(".tmp"):
                    barrier.wait(timeout=2)
                return original_replace(self, other)

            def writer(seq: int):
                try:
                    _atomic_write_json(target, {"seq": seq})
                except Exception as exc:  # pragma: no cover - asserted below
                    errors.append(exc)

            with patch("pathlib.Path.replace", new=patched_replace):
                t1 = threading.Thread(target=writer, args=(1,))
                t2 = threading.Thread(target=writer, args=(2,))
                t1.start()
                t2.start()
                t1.join()
                t2.join()

            self.assertEqual(errors, [])
            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn(saved.get("seq"), {1, 2})

    def test_write_teacher_session_records_handles_concurrent_writers(self):
        with TemporaryDirectory() as td:
            target = Path(td) / "data" / "teacher_chat_sessions" / "teacher_demo" / "session_main.jsonl"
            barrier = threading.Barrier(2)
            errors = []

            original_replace = Path.replace

            def patched_replace(self: Path, other):
                if self.parent == target.parent and self.name.startswith("session_main.jsonl") and self.name.endswith(".tmp"):
                    barrier.wait(timeout=2)
                return original_replace(self, other)

            records_a = [{"ts": "2026-02-07T23:00:00", "role": "user", "content": "A"}]
            records_b = [{"ts": "2026-02-07T23:00:01", "role": "assistant", "content": "B"}]

            def writer(records):
                try:
                    write_teacher_session_records(target, records)
                except Exception as exc:  # pragma: no cover - asserted below
                    errors.append(exc)

            with patch("pathlib.Path.replace", new=patched_replace):
                t1 = threading.Thread(target=writer, args=(records_a,))
                t2 = threading.Thread(target=writer, args=(records_b,))
                t1.start()
                t2.start()
                t1.join()
                t2.join()

            self.assertEqual(errors, [])
            lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            obj = json.loads(lines[0])
            self.assertIn(obj.get("content"), {"A", "B"})


if __name__ == "__main__":
    unittest.main()
