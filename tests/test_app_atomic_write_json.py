import importlib
import json
import os
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class AppAtomicWriteJsonTest(unittest.TestCase):
    def test_atomic_write_json_handles_concurrent_writers(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
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
                    app_mod._atomic_write_json(target, {"seq": seq})
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


if __name__ == "__main__":
    unittest.main()
