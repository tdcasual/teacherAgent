import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.api.chat_lock_service import (
    ChatLockDeps,
    chat_job_claim_path,
    release_lockfile,
    try_acquire_lockfile,
)


class ChatLockServiceTest(unittest.TestCase):
    def test_try_acquire_lockfile_success_then_conflict(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            deps = ChatLockDeps(
                now_ts=time.time,
                now_iso=lambda: "2026-01-01T00:00:00",
                get_pid=lambda: 1234,
                is_pid_alive=lambda _pid: True,
            )
            self.assertTrue(try_acquire_lockfile(path, ttl_sec=60, deps=deps))
            self.assertTrue(path.exists())
            self.assertFalse(try_acquire_lockfile(path, ttl_sec=60, deps=deps))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(str(payload.get("owner") or ""), str)
            self.assertTrue(str(payload.get("owner") or "").strip())

    def test_try_acquire_lockfile_reclaims_stale_lock(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("stale", encoding="utf-8")
            stale_ts = 1000.0
            os.utime(path, (stale_ts, stale_ts))
            deps = ChatLockDeps(now_ts=lambda: 2000.0, now_iso=lambda: "2026-01-01T00:00:00", get_pid=lambda: 4321)
            self.assertTrue(try_acquire_lockfile(path, ttl_sec=100, deps=deps))
            self.assertTrue(path.exists())

    def test_try_acquire_lockfile_reclaims_dead_pid_lock_even_if_not_stale(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"pid": 9999, "ts": "2026-01-01T00:00:00"}), encoding="utf-8")
            now_ts = 2000.0
            os.utime(path, (now_ts, now_ts))
            deps = ChatLockDeps(now_ts=lambda: now_ts + 1, now_iso=lambda: "2026-01-01T00:00:01", get_pid=lambda: 4321)
            with patch("services.api.chat_lock_service.os.kill", side_effect=ProcessLookupError):
                self.assertTrue(try_acquire_lockfile(path, ttl_sec=3600, deps=deps))
                self.assertTrue(path.exists())

    def test_try_acquire_lockfile_does_not_reclaim_alive_pid_even_if_ttl_expired(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"pid": 7777, "ts": "2026-01-01T00:00:00"}), encoding="utf-8")
            os.utime(path, (1000.0, 1000.0))
            deps = ChatLockDeps(
                now_ts=lambda: 2000.0,
                now_iso=lambda: "2026-01-01T00:00:01",
                get_pid=lambda: 4321,
                is_pid_alive=lambda _pid: True,
            )
            self.assertFalse(try_acquire_lockfile(path, ttl_sec=100, deps=deps))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(int(payload.get("pid") or 0), 7777)

    def test_release_lockfile_is_idempotent(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("lock", encoding="utf-8")
            release_lockfile(path)
            self.assertFalse(path.exists())
            release_lockfile(path)
            self.assertFalse(path.exists())

    def test_release_lockfile_keeps_file_when_owner_mismatch(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            deps = ChatLockDeps(
                now_ts=time.time,
                now_iso=lambda: "2026-01-01T00:00:00",
                get_pid=lambda: 1234,
                is_pid_alive=lambda _pid: True,
            )
            self.assertTrue(try_acquire_lockfile(path, ttl_sec=60, deps=deps))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["owner"] = "other-owner-token"
            path.write_text(json.dumps(payload), encoding="utf-8")

            release_lockfile(path)
            self.assertTrue(path.exists())

    def test_chat_job_claim_path_uses_job_directory(self):
        claim = chat_job_claim_path("job_1", lambda job_id: Path("/tmp/chat_jobs") / job_id)
        self.assertEqual(str(claim), "/tmp/chat_jobs/job_1/claim.lock")


if __name__ == "__main__":
    unittest.main()
