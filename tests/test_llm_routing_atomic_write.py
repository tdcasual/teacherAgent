import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.api import llm_routing


class LlmRoutingAtomicWriteTest(unittest.TestCase):
    def test_atomic_write_json_handles_concurrent_writers(self):
        with TemporaryDirectory() as td:
            target = Path(td) / "llm_routing.json"
            barrier = threading.Barrier(2)
            errors = []

            original_replace = Path.replace

            def patched_replace(self: Path, other):
                if self.parent == target.parent and self.name.startswith("llm_routing.json") and self.name.endswith(".tmp"):
                    barrier.wait(timeout=2)
                return original_replace(self, other)

            def writer(version: int):
                try:
                    llm_routing._atomic_write_json(target, {"schema_version": 1, "version": version})
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
            self.assertIn(saved.get("version"), {1, 2})


if __name__ == "__main__":
    unittest.main()
