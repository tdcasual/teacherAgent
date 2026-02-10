import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.api.job_repository import _release_lockfile, _try_acquire_lockfile


class JobRepositoryLockfileTest(unittest.TestCase):
    def test_try_acquire_lockfile_reclaims_dead_pid_lock_even_if_not_stale(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"pid": 9999, "ts": "2026-01-01T00:00:00"}), encoding="utf-8")
            now_ts = 2000.0
            os.utime(path, (now_ts, now_ts))
            with patch("services.api.job_repository.time.time", return_value=now_ts + 1):
                with patch("services.api.job_repository.os.kill", side_effect=ProcessLookupError):
                    self.assertTrue(_try_acquire_lockfile(path, ttl_sec=3600))
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    self.assertIn("pid", payload)
                    self.assertIn("ts", payload)

    def test_release_lockfile_is_idempotent(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("lock", encoding="utf-8")
            _release_lockfile(path)
            self.assertFalse(path.exists())
            _release_lockfile(path)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
