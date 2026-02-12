"""Tests for chart_sandbox module."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from services.api.chart_sandbox import (
    PROFILES,
    build_filesystem_guard_source,
    build_sanitized_env,
    make_preexec_fn,
    scan_code_patterns,
)


class BuildSanitizedEnvTest(unittest.TestCase):
    def test_sandboxed_only_whitelist(self):
        with patch.dict(os.environ, {"PATH": "/usr/bin", "SECRET_KEY": "abc", "HOME": "/home"}, clear=True):
            env = build_sanitized_env("sandboxed")
            self.assertIn("PATH", env)
            self.assertIn("HOME", env)
            self.assertNotIn("SECRET_KEY", env)

    def test_trusted_strips_sensitive(self):
        with patch.dict(os.environ, {"PATH": "/usr/bin", "AWS_SECRET": "x", "MY_VAR": "y"}, clear=True):
            env = build_sanitized_env("trusted")
            self.assertIn("PATH", env)
            self.assertIn("MY_VAR", env)
            self.assertNotIn("AWS_SECRET", env)

    def test_template_strips_sensitive(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://x", "LANG": "en"}, clear=True):
            env = build_sanitized_env("template")
            self.assertNotIn("REDIS_URL", env)
            self.assertIn("LANG", env)

    def test_unknown_profile_defaults_to_trusted(self):
        with patch.dict(os.environ, {"API_KEY_X": "secret", "LANG": "en"}, clear=True):
            env = build_sanitized_env("unknown")
            self.assertNotIn("API_KEY_X", env)
            self.assertIn("LANG", env)

    def test_sandboxed_whitelist_includes_data_dir(self):
        with patch.dict(os.environ, {"DATA_DIR": "/app/data", "PASSWORD": "x"}, clear=True):
            env = build_sanitized_env("sandboxed")
            self.assertIn("DATA_DIR", env)
            self.assertNotIn("PASSWORD", env)

    def test_sensitive_patterns_stripped(self):
        sensitive_keys = ["SECRET_KEY", "DB_PASSWORD", "MASTER_KEY_V2", "MY_API_KEY", "AUTH_TOKEN", "OSS_ENDPOINT"]
        with patch.dict(os.environ, {k: "val" for k in sensitive_keys}, clear=True):
            env = build_sanitized_env("trusted")
            for k in sensitive_keys:
                self.assertNotIn(k, env, f"{k} should be stripped")


class MakePreexecFnTest(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "Unix only")
    def test_returns_callable_on_unix(self):
        fn = make_preexec_fn("sandboxed", 60)
        self.assertIsNotNone(fn)
        self.assertTrue(callable(fn))

    @unittest.skipIf(sys.platform == "win32", "Unix only")
    def test_trusted_has_higher_limits(self):
        fn_sand = make_preexec_fn("sandboxed", 60)
        fn_trust = make_preexec_fn("trusted", 60)
        self.assertIsNotNone(fn_sand)
        self.assertIsNotNone(fn_trust)

    def test_unknown_profile_uses_trusted_defaults(self):
        fn = make_preexec_fn("unknown_profile", 60)
        if sys.platform != "win32":
            self.assertIsNotNone(fn)


class ScanCodePatternsTest(unittest.TestCase):
    def test_clean_code_passes(self):
        result = scan_code_patterns("import matplotlib\nplt.plot([1,2,3])", "sandboxed")
        self.assertIsNone(result)

    def test_os_system_blocked(self):
        result = scan_code_patterns("os.system('rm -rf /')", "sandboxed")
        self.assertIsNotNone(result)
        self.assertIn("os.system", result["violations"])

    def test_subprocess_blocked(self):
        result = scan_code_patterns("import subprocess\nsubprocess.run(['ls'])", "sandboxed")
        self.assertIsNotNone(result)
        self.assertIn("subprocess", result["violations"])

    def test_exec_blocked(self):
        result = scan_code_patterns("exec('print(1)')", "sandboxed")
        self.assertIsNotNone(result)
        self.assertIn("exec()", result["violations"])

    def test_eval_blocked(self):
        result = scan_code_patterns("x = eval('1+1')", "sandboxed")
        self.assertIsNotNone(result)

    def test_dunder_import_blocked(self):
        result = scan_code_patterns("m = __import__('os')", "sandboxed")
        self.assertIsNotNone(result)

    def test_socket_blocked(self):
        result = scan_code_patterns("import socket\ns = socket.socket()", "sandboxed")
        self.assertIsNotNone(result)

    def test_shutil_rmtree_blocked(self):
        result = scan_code_patterns("shutil.rmtree('/tmp/x')", "sandboxed")
        self.assertIsNotNone(result)

    def test_os_environ_blocked(self):
        result = scan_code_patterns("key = os.environ['SECRET']", "sandboxed")
        self.assertIsNotNone(result)

    def test_ctypes_blocked(self):
        result = scan_code_patterns("import ctypes", "sandboxed")
        self.assertIsNotNone(result)

    def test_trusted_profile_skips_scan(self):
        result = scan_code_patterns("os.system('rm -rf /')", "trusted")
        self.assertIsNone(result)

    def test_template_profile_skips_scan(self):
        result = scan_code_patterns("import subprocess", "template")
        self.assertIsNone(result)

    def test_multiple_violations(self):
        code = "import subprocess\nos.system('x')\neval('y')"
        result = scan_code_patterns(code, "sandboxed")
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result["violations"]), 3)

    def test_os_remove_blocked(self):
        result = scan_code_patterns("os.remove('/etc/passwd')", "sandboxed")
        self.assertIsNotNone(result)

    def test_os_popen_blocked(self):
        result = scan_code_patterns("os.popen('ls')", "sandboxed")
        self.assertIsNotNone(result)

    def test_signal_module_blocked(self):
        result = scan_code_patterns("signal.alarm(5)", "sandboxed")
        self.assertIsNotNone(result)


class BuildFilesystemGuardSourceTest(unittest.TestCase):
    def test_returns_valid_python(self):
        source = build_filesystem_guard_source("/tmp/out", ["/tmp/out", "/data"])
        compile(source, "<test>", "exec")

    def test_guard_patches_open(self):
        source = build_filesystem_guard_source("/tmp/out", ["/tmp/out"])
        self.assertIn("_guarded_open", source)
        self.assertIn("builtins", source)

    def test_guard_contains_output_dir(self):
        source = build_filesystem_guard_source("/my/output", ["/my/output"])
        self.assertIn("/my/output", source)

    def test_guard_contains_allowed_roots(self):
        source = build_filesystem_guard_source("/out", ["/out", "/data", "/uploads"])
        self.assertIn("/data", source)
        self.assertIn("/uploads", source)


class ConcurrencySemaphoreTest(unittest.TestCase):
    def test_semaphore_exists(self):
        from services.api.global_limits import GLOBAL_CHART_EXEC_SEMAPHORE
        self.assertIsNotNone(GLOBAL_CHART_EXEC_SEMAPHORE)

    def test_semaphore_acquire_release(self):
        from services.api.global_limits import GLOBAL_CHART_EXEC_SEMAPHORE
        acquired = GLOBAL_CHART_EXEC_SEMAPHORE.acquire(timeout=1)
        self.assertTrue(acquired)
        GLOBAL_CHART_EXEC_SEMAPHORE.release()


class ProfilesTest(unittest.TestCase):
    def test_all_profiles_defined(self):
        self.assertIn("template", PROFILES)
        self.assertIn("trusted", PROFILES)
        self.assertIn("sandboxed", PROFILES)


if __name__ == "__main__":
    unittest.main()
