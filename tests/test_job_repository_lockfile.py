import json
import os
import re
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from services.api.chat_lock_service import (
    ChatLockDeps,
    release_lockfile as _shared_release_lockfile,
    try_acquire_lockfile as _shared_try_acquire_lockfile,
)
from services.api.job_repository import _release_lockfile, _try_acquire_lockfile


class JobRepositoryLockfileTest(unittest.TestCase):
    def _run_parallel(self, fn, workers: int = 16):
        gate = threading.Barrier(workers)
        results = []
        errors = []
        guard = threading.Lock()

        def worker():
            try:
                gate.wait(timeout=2)
                value = fn()
                with guard:
                    results.append(bool(value))
            except Exception as exc:  # pragma: no cover - defensive
                with guard:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

        self.assertFalse(errors, f"parallel run errors: {errors}")
        self.assertEqual(len(results), workers)
        return results

    def test_try_acquire_lockfile_delegates_to_shared_impl_with_expected_deps(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            with patch("services.api.job_repository.time.time", return_value=1234.0):
                with patch("services.api.job_repository.os.getpid", return_value=5678):
                    with patch("services.api.job_repository._try_acquire_lockfile_impl", return_value=True) as mocked:
                        self.assertTrue(_try_acquire_lockfile(path, ttl_sec=12))
                        mocked.assert_called_once()

                        called_path, called_ttl, called_deps = mocked.call_args.args
                        self.assertEqual(called_path, path)
                        self.assertEqual(called_ttl, 12)
                        self.assertIsInstance(called_deps, ChatLockDeps)
                        self.assertEqual(called_deps.now_ts(), 1234.0)
                        self.assertEqual(called_deps.get_pid(), 5678)

                        ts = called_deps.now_iso()
                        self.assertIsInstance(ts, str)
                        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2}T")

                        with patch("services.api.job_repository.os.kill", side_effect=ProcessLookupError):
                            self.assertFalse(called_deps.is_pid_alive(9999))

    def test_release_lockfile_delegates_to_shared_impl(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            with patch("services.api.job_repository._release_lockfile_impl") as mocked:
                _release_lockfile(path)
                mocked.assert_called_once_with(path)

    def test_job_repository_lock_helpers_only_expose_shared_api(self):
        import services.api.job_repository as mod

        self.assertTrue(hasattr(mod, "_try_acquire_lockfile"))
        self.assertTrue(hasattr(mod, "_release_lockfile"))
        self.assertFalse(hasattr(mod, "_read_lock_pid"))

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

    def test_try_acquire_lockfile_success_then_conflict(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            self.assertTrue(_try_acquire_lockfile(path, ttl_sec=60))
            self.assertTrue(path.exists())
            self.assertFalse(_try_acquire_lockfile(path, ttl_sec=60))

    def test_try_acquire_lockfile_reclaims_stale_lock(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("stale", encoding="utf-8")
            stale_ts = 1000.0
            os.utime(path, (stale_ts, stale_ts))
            with patch("services.api.job_repository.time.time", return_value=2000.0):
                self.assertTrue(_try_acquire_lockfile(path, ttl_sec=100))
                self.assertTrue(path.exists())

    def test_release_lockfile_is_idempotent(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "claim.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("lock", encoding="utf-8")
            _release_lockfile(path)
            self.assertFalse(path.exists())
            _release_lockfile(path)
            self.assertFalse(path.exists())

    def test_job_and_shared_impl_success_then_conflict_contract_match(self):
        with TemporaryDirectory() as td:
            job_path = Path(td) / "job_claim.lock"
            shared_path = Path(td) / "shared_claim.lock"
            shared_deps = ChatLockDeps(
                now_ts=time.time,
                now_iso=lambda: "2026-01-01T00:00:00",
                get_pid=lambda: 2222,
                is_pid_alive=lambda _pid: True,
            )

            job_seq = [_try_acquire_lockfile(job_path, ttl_sec=60), _try_acquire_lockfile(job_path, ttl_sec=60)]
            shared_seq = [
                _shared_try_acquire_lockfile(shared_path, ttl_sec=60, deps=shared_deps),
                _shared_try_acquire_lockfile(shared_path, ttl_sec=60, deps=shared_deps),
            ]

            self.assertEqual(job_seq, [True, False])
            self.assertEqual(shared_seq, [True, False])

    def test_job_and_shared_impl_stale_reclaim_contract_match(self):
        with TemporaryDirectory() as td:
            job_path = Path(td) / "job_claim.lock"
            shared_path = Path(td) / "shared_claim.lock"
            for lock_path in (job_path, shared_path):
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                lock_path.write_text("stale", encoding="utf-8")
                os.utime(lock_path, (1000.0, 1000.0))

            with patch("services.api.job_repository.time.time", return_value=2000.0):
                job_ok = _try_acquire_lockfile(job_path, ttl_sec=100)

            shared_deps = ChatLockDeps(
                now_ts=lambda: 2000.0,
                now_iso=lambda: "2026-01-01T00:00:00",
                get_pid=lambda: 3333,
                is_pid_alive=lambda _pid: True,
            )
            shared_ok = _shared_try_acquire_lockfile(shared_path, ttl_sec=100, deps=shared_deps)

            self.assertTrue(job_ok)
            self.assertTrue(shared_ok)

    def test_job_and_shared_impl_dead_pid_reclaim_contract_match(self):
        with TemporaryDirectory() as td:
            job_path = Path(td) / "job_claim.lock"
            shared_path = Path(td) / "shared_claim.lock"
            payload = json.dumps({"pid": 9999, "ts": "2026-01-01T00:00:00"})
            for lock_path in (job_path, shared_path):
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                lock_path.write_text(payload, encoding="utf-8")
                os.utime(lock_path, (2000.0, 2000.0))

            with patch("services.api.job_repository.time.time", return_value=2001.0):
                with patch("services.api.job_repository.os.kill", side_effect=ProcessLookupError):
                    job_ok = _try_acquire_lockfile(job_path, ttl_sec=3600)

            shared_deps = ChatLockDeps(
                now_ts=lambda: 2001.0,
                now_iso=lambda: "2026-01-01T00:00:01",
                get_pid=lambda: 4444,
            )
            with patch("services.api.chat_lock_service.os.kill", side_effect=ProcessLookupError):
                shared_ok = _shared_try_acquire_lockfile(shared_path, ttl_sec=3600, deps=shared_deps)

            self.assertTrue(job_ok)
            self.assertTrue(shared_ok)

            job_payload = json.loads(job_path.read_text(encoding="utf-8"))
            shared_payload = json.loads(shared_path.read_text(encoding="utf-8"))
            self.assertTrue(re.match(r"\d{4}-\d{2}-\d{2}T", str(job_payload.get("ts") or "")))
            self.assertTrue(re.match(r"\d{4}-\d{2}-\d{2}T", str(shared_payload.get("ts") or "")))

    def test_job_and_shared_release_are_both_idempotent(self):
        with TemporaryDirectory() as td:
            job_path = Path(td) / "job_claim.lock"
            shared_path = Path(td) / "shared_claim.lock"
            for lock_path in (job_path, shared_path):
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                lock_path.write_text("lock", encoding="utf-8")

            _release_lockfile(job_path)
            _release_lockfile(job_path)
            self.assertFalse(job_path.exists())

            _shared_release_lockfile(shared_path)
            _shared_release_lockfile(shared_path)
            self.assertFalse(shared_path.exists())

    def test_job_repository_lock_contention_matrix(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "job_claim.lock"

            acquire = lambda: _try_acquire_lockfile(path, ttl_sec=60)

            # Empty lock: exactly one contender should win.
            first_round = self._run_parallel(acquire, workers=24)
            self.assertEqual(sum(first_round), 1)
            self.assertTrue(path.exists())

            # While held: no contender should win.
            held_round = self._run_parallel(acquire, workers=24)
            self.assertEqual(sum(held_round), 0)

            # After release: exactly one contender should win again.
            _release_lockfile(path)
            self.assertFalse(path.exists())
            second_round = self._run_parallel(acquire, workers=24)
            self.assertEqual(sum(second_round), 1)
            self.assertTrue(path.exists())

    def test_shared_lock_contention_matrix(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "shared_claim.lock"
            deps = ChatLockDeps(
                now_ts=time.time,
                now_iso=lambda: "2026-01-01T00:00:00",
                get_pid=os.getpid,
                is_pid_alive=lambda _pid: True,
            )

            acquire = lambda: _shared_try_acquire_lockfile(path, ttl_sec=60, deps=deps)

            first_round = self._run_parallel(acquire, workers=24)
            self.assertEqual(sum(first_round), 1)
            self.assertTrue(path.exists())

            held_round = self._run_parallel(acquire, workers=24)
            self.assertEqual(sum(held_round), 0)

            _shared_release_lockfile(path)
            self.assertFalse(path.exists())
            second_round = self._run_parallel(acquire, workers=24)
            self.assertEqual(sum(second_round), 1)
            self.assertTrue(path.exists())

    @pytest.mark.stress
    @unittest.skipUnless(
        os.getenv("RUN_STRESS_TESTS", "").strip().lower() in {"1", "true", "yes", "on"},
        "stress test disabled; set RUN_STRESS_TESTS=1",
    )
    def test_stress_job_repository_lock_contention(self):
        rounds = int(os.getenv("LOCK_STRESS_ROUNDS", "60") or 60)
        workers = int(os.getenv("LOCK_STRESS_WORKERS", "32") or 32)
        rounds = max(10, min(rounds, 300))
        workers = max(8, min(workers, 128))

        with TemporaryDirectory() as td:
            path = Path(td) / "job_claim.lock"
            acquire = lambda: _try_acquire_lockfile(path, ttl_sec=60)

            for idx in range(rounds):
                _release_lockfile(path)

                first_round = self._run_parallel(acquire, workers=workers)
                self.assertEqual(sum(first_round), 1, f"first_round failed at iteration={idx}")
                self.assertTrue(path.exists(), f"lock missing after acquire at iteration={idx}")

                held_round = self._run_parallel(acquire, workers=workers)
                self.assertEqual(sum(held_round), 0, f"held_round failed at iteration={idx}")

                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    self.fail(f"invalid lock payload at iteration={idx}: {exc}")
                self.assertIn("pid", payload)
                self.assertIn("ts", payload)

            _release_lockfile(path)
            self.assertFalse(path.exists())

    @pytest.mark.stress
    @unittest.skipUnless(
        os.getenv("RUN_STRESS_TESTS", "").strip().lower() in {"1", "true", "yes", "on"},
        "stress test disabled; set RUN_STRESS_TESTS=1",
    )
    def test_stress_job_and_shared_contract_alignment(self):
        rounds = int(os.getenv("LOCK_STRESS_ROUNDS", "40") or 40)
        workers = int(os.getenv("LOCK_STRESS_WORKERS", "24") or 24)
        rounds = max(10, min(rounds, 200))
        workers = max(8, min(workers, 96))

        with TemporaryDirectory() as td:
            job_path = Path(td) / "job_claim.lock"
            shared_path = Path(td) / "shared_claim.lock"
            deps = ChatLockDeps(
                now_ts=time.time,
                now_iso=lambda: "2026-01-01T00:00:00",
                get_pid=os.getpid,
                is_pid_alive=lambda _pid: True,
            )

            job_acquire = lambda: _try_acquire_lockfile(job_path, ttl_sec=60)
            shared_acquire = lambda: _shared_try_acquire_lockfile(shared_path, ttl_sec=60, deps=deps)

            for idx in range(rounds):
                _release_lockfile(job_path)
                _shared_release_lockfile(shared_path)

                job_first = self._run_parallel(job_acquire, workers=workers)
                shared_first = self._run_parallel(shared_acquire, workers=workers)
                self.assertEqual(sum(job_first), 1, f"job_first failed at iteration={idx}")
                self.assertEqual(sum(shared_first), 1, f"shared_first failed at iteration={idx}")

                job_held = self._run_parallel(job_acquire, workers=workers)
                shared_held = self._run_parallel(shared_acquire, workers=workers)
                self.assertEqual(sum(job_held), 0, f"job_held failed at iteration={idx}")
                self.assertEqual(sum(shared_held), 0, f"shared_held failed at iteration={idx}")

            _release_lockfile(job_path)
            _shared_release_lockfile(shared_path)


if __name__ == "__main__":
    unittest.main()
