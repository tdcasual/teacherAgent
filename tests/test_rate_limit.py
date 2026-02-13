"""Tests for services.api.rate_limit sliding-window middleware."""
from __future__ import annotations

import asyncio
import os
import time
import unittest
from collections import defaultdict, deque
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import services.api.rate_limit as rl_mod


def _make_request(path="/api/test", client_host="10.0.0.1", forwarded_for=None):
    """Build a minimal mock Request with url.path, headers, client.host."""
    headers = {}
    if forwarded_for is not None:
        headers["x-forwarded-for"] = forwarded_for
    url = SimpleNamespace(path=path)
    client = SimpleNamespace(host=client_host)
    req = SimpleNamespace(url=url, headers=headers, client=client)
    return req


def _ok_response():
    return SimpleNamespace(status_code=200)


class TestClientKey(unittest.TestCase):
    def setUp(self):
        self._orig_trust = rl_mod._trust_x_forwarded_for
        self._orig_trusted = set(rl_mod._trusted_proxy_ips)

    def tearDown(self):
        rl_mod._trust_x_forwarded_for = self._orig_trust
        rl_mod._trusted_proxy_ips = set(self._orig_trusted)

    def test_uses_x_forwarded_for_first_ip_when_trusted(self):
        rl_mod._trust_x_forwarded_for = True
        rl_mod._trusted_proxy_ips = set()
        req = _make_request(forwarded_for="1.2.3.4, 5.6.7.8")
        self.assertEqual(rl_mod._client_key(req), "1.2.3.4")

    def test_strips_whitespace_from_forwarded(self):
        rl_mod._trust_x_forwarded_for = True
        rl_mod._trusted_proxy_ips = set()
        req = _make_request(forwarded_for="  9.8.7.6 , 1.1.1.1")
        self.assertEqual(rl_mod._client_key(req), "9.8.7.6")

    def test_does_not_trust_forwarded_for_by_default(self):
        rl_mod._trust_x_forwarded_for = False
        rl_mod._trusted_proxy_ips = set()
        req = _make_request(client_host="192.168.1.1", forwarded_for="9.8.7.6")
        self.assertEqual(rl_mod._client_key(req), "192.168.1.1")

    def test_trusts_forwarded_for_only_from_trusted_proxy(self):
        rl_mod._trust_x_forwarded_for = True
        rl_mod._trusted_proxy_ips = {"127.0.0.1"}
        req = _make_request(client_host="10.0.0.2", forwarded_for="9.8.7.6")
        self.assertEqual(rl_mod._client_key(req), "10.0.0.2")

        req_trusted = _make_request(client_host="127.0.0.1", forwarded_for="9.8.7.6")
        self.assertEqual(rl_mod._client_key(req_trusted), "9.8.7.6")

    def test_falls_back_to_client_host(self):
        req = _make_request(client_host="192.168.1.1")
        self.assertEqual(rl_mod._client_key(req), "192.168.1.1")

    def test_unknown_when_no_client(self):
        req = _make_request()
        req.client = None
        self.assertEqual(rl_mod._client_key(req), "unknown")


# ---------------------------------------------------------------------------
# Helpers for middleware tests
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestRateLimitMiddleware(unittest.TestCase):
    """Tests that exercise the actual rate-limiting logic."""

    def setUp(self):
        # Reset buckets for isolation.
        self._original_rpm = rl_mod._rpm
        self._original_buckets = rl_mod._buckets
        self._original_last_seen = rl_mod._bucket_last_seen
        self._original_max_buckets = rl_mod._max_buckets
        rl_mod._buckets = defaultdict(deque)
        rl_mod._bucket_last_seen = {}
        rl_mod._max_buckets = 4096
        # Patch os.getenv so PYTEST_CURRENT_TEST returns None inside the middleware
        self._patcher = patch.object(
            rl_mod.os, "getenv", side_effect=lambda k, *a: None if k == "PYTEST_CURRENT_TEST" else os.getenv(k, *a)
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        rl_mod._rpm = self._original_rpm
        rl_mod._buckets = self._original_buckets
        rl_mod._bucket_last_seen = self._original_last_seen
        rl_mod._max_buckets = self._original_max_buckets

    # -- basic pass-through --

    def test_request_within_limit_passes(self):
        rl_mod._rpm = 5
        req = _make_request()
        call_next = AsyncMock(return_value=_ok_response())
        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 200)
        call_next.assert_awaited_once_with(req)

    # -- 429 when over limit --

    def test_over_limit_returns_429(self):
        rl_mod._rpm = 3
        req = _make_request(client_host="10.0.0.99")
        call_next = AsyncMock(return_value=_ok_response())

        # Fill the bucket to the limit
        now = time.monotonic()
        bucket = rl_mod._buckets["10.0.0.99"]
        for i in range(3):
            bucket.append(now - 10 + i)

        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 429)
        body = resp.body.decode()
        self.assertIn("rate_limit_exceeded", body)
        call_next.assert_not_awaited()

    def test_429_includes_retry_after_header(self):
        rl_mod._rpm = 2
        req = _make_request(client_host="10.0.0.50")
        call_next = AsyncMock(return_value=_ok_response())

        now = time.monotonic()
        bucket = rl_mod._buckets["10.0.0.50"]
        bucket.append(now - 30)
        bucket.append(now - 10)

        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 429)
        retry = resp.headers.get("retry-after")
        self.assertIsNotNone(retry)
        self.assertGreater(int(retry), 0)

    # -- /health bypass --

    def test_health_path_bypasses_rate_limit(self):
        rl_mod._rpm = 1
        # Fill bucket so a normal request would be blocked
        bucket = rl_mod._buckets["10.0.0.1"]
        bucket.append(time.monotonic())

        req = _make_request(path="/health")
        call_next = AsyncMock(return_value=_ok_response())
        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 200)
        call_next.assert_awaited_once()

    def test_health_trailing_slash_bypasses(self):
        rl_mod._rpm = 1
        bucket = rl_mod._buckets["10.0.0.1"]
        bucket.append(time.monotonic())

        req = _make_request(path="/health/")
        call_next = AsyncMock(return_value=_ok_response())
        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 200)

    # -- RPM=0 disables --

    def test_rpm_zero_disables_rate_limiting(self):
        rl_mod._rpm = 0
        req = _make_request()
        call_next = AsyncMock(return_value=_ok_response())
        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 200)
        call_next.assert_awaited_once()

    def test_rpm_negative_disables_rate_limiting(self):
        rl_mod._rpm = -1
        req = _make_request()
        call_next = AsyncMock(return_value=_ok_response())
        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 200)

    # -- sliding window eviction --

    @patch("services.api.rate_limit.time")
    def test_old_entries_evicted_after_window(self, mock_time):
        rl_mod._rpm = 2
        # First two requests at t=100
        mock_time.monotonic.return_value = 100.0
        req = _make_request(client_host="10.0.0.77")
        call_next = AsyncMock(return_value=_ok_response())

        bucket = rl_mod._buckets["10.0.0.77"]
        bucket.append(100.0)
        bucket.append(100.5)

        # At t=100.5 the bucket is full → 429
        mock_time.monotonic.return_value = 100.8
        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 429)

        # At t=161 (>60s later) old entries should be evicted → passes
        mock_time.monotonic.return_value = 161.0
        call_next.reset_mock()
        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 200)
        call_next.assert_awaited_once()

    # -- per-client isolation --

    def test_separate_buckets_per_client(self):
        rl_mod._rpm = 1
        call_next = AsyncMock(return_value=_ok_response())

        req_a = _make_request(client_host="10.0.0.1")
        req_b = _make_request(client_host="10.0.0.2")

        # First request from client A passes
        resp = _run(rl_mod.rate_limit_middleware(req_a, call_next))
        self.assertEqual(resp.status_code, 200)

        # Client A is now at limit → 429
        resp = _run(rl_mod.rate_limit_middleware(req_a, call_next))
        self.assertEqual(resp.status_code, 429)

        # Client B still has room → 200
        call_next.reset_mock()
        resp = _run(rl_mod.rate_limit_middleware(req_b, call_next))
        self.assertEqual(resp.status_code, 200)

    def test_empty_bucket_is_removed_after_window(self):
        rl_mod._rpm = 2
        req = _make_request(client_host="10.0.0.88")
        call_next = AsyncMock(return_value=_ok_response())

        bucket = rl_mod._buckets["10.0.0.88"]
        bucket.append(time.monotonic() - 120.0)
        rl_mod._bucket_last_seen["10.0.0.88"] = time.monotonic() - 120.0

        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("10.0.0.88", rl_mod._buckets)
        self.assertEqual(len(rl_mod._buckets["10.0.0.88"]), 1)

    def test_enforces_max_bucket_count_by_evicting_oldest(self):
        rl_mod._rpm = 10
        rl_mod._max_buckets = 2
        now = time.monotonic()
        rl_mod._buckets["a"].append(now - 2.0)
        rl_mod._buckets["b"].append(now - 1.0)
        rl_mod._bucket_last_seen["a"] = now - 2.0
        rl_mod._bucket_last_seen["b"] = now - 1.0

        req = _make_request(client_host="c")
        call_next = AsyncMock(return_value=_ok_response())
        resp = _run(rl_mod.rate_limit_middleware(req, call_next))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("a", rl_mod._buckets)
        self.assertIn("b", rl_mod._buckets)
        self.assertIn("c", rl_mod._buckets)


if __name__ == "__main__":
    unittest.main()
