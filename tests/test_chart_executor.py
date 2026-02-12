"""Tests for chart_executor pure helpers and filesystem resolvers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.api.chart_executor import (
    _build_runner_source,
    _chart_envs_root,
    _clip_text,
    _env_python_path,
    _env_root,
    _extract_missing_module,
    _mark_chart_env_used,
    _normalize_bool,
    _normalize_packages,
    _normalize_retries,
    _normalize_timeout,
    _prune_chart_envs,
    _safe_any_file_name,
    _safe_file_name,
    _safe_run_id,
    _venv_scope,
    resolve_chart_image_path,
    resolve_chart_run_meta_path,
)

# ---------------------------------------------------------------------------
# _safe_run_id
# ---------------------------------------------------------------------------

class TestSafeRunId:
    @pytest.mark.parametrize("val,expected", [
        (None, None),
        ("", None),
        ("   ", None),
        ("abcd1234", "abcd1234"),
        ("chr_abc123def4", "chr_abc123def4"),
        ("A-B_c-9" * 5, "A-B_c-9" * 5),  # 40 chars, within 8-80
        ("short", None),  # 5 chars < 8
        ("12345678", "12345678"),  # exactly 8
    ])
    def test_basic(self, val, expected):
        assert _safe_run_id(val) == expected

    def test_rejects_special_chars(self):
        assert _safe_run_id("abc/../../etc") is None
        assert _safe_run_id("run id!@#") is None

    def test_too_long(self):
        assert _safe_run_id("a" * 81) is None

    def test_exactly_80(self):
        assert _safe_run_id("a" * 80) == "a" * 80

    def test_strips_whitespace(self):
        assert _safe_run_id("  abcd1234  ") == "abcd1234"


# ---------------------------------------------------------------------------
# _safe_file_name
# ---------------------------------------------------------------------------

class TestSafeFileName:
    def test_default_on_none(self):
        assert _safe_file_name(None) == "main.png"

    def test_default_on_empty(self):
        assert _safe_file_name("") == "main.png"

    def test_appends_png(self):
        assert _safe_file_name("chart") == "chart.png"

    def test_keeps_png(self):
        assert _safe_file_name("chart.png") == "chart.png"

    def test_case_insensitive_png(self):
        assert _safe_file_name("chart.PNG") == "chart.PNG"

    def test_strips_path_traversal(self):
        # Path("../../evil.png").name == "evil.png"
        assert _safe_file_name("../../evil.png") == "evil.png"

    def test_rejects_bad_chars(self):
        assert _safe_file_name("bad file!.png") == "main.png"

    def test_custom_default(self):
        assert _safe_file_name(None, default="out.png") == "out.png"

    def test_name_starting_with_dot(self):
        # _FILE_RE requires first char [A-Za-z0-9]
        assert _safe_file_name(".hidden.png") == "main.png"


# ---------------------------------------------------------------------------
# _safe_any_file_name
# ---------------------------------------------------------------------------

class TestSafeAnyFileName:
    @pytest.mark.parametrize("val,expected", [
        (None, None),
        ("", None),
        ("data.csv", "data.csv"),
        ("../../etc/passwd", "passwd"),
        (".hidden", None),  # starts with dot
    ])
    def test_basic(self, val, expected):
        assert _safe_any_file_name(val) == expected

    def test_rejects_special(self):
        assert _safe_any_file_name("bad name!") is None


# ---------------------------------------------------------------------------
# _clip_text
# ---------------------------------------------------------------------------

class TestClipText:
    def test_short_unchanged(self):
        assert _clip_text("hello") == "hello"

    def test_exact_limit(self):
        text = "x" * 60000
        assert _clip_text(text) == text

    def test_over_limit(self):
        text = "x" * 60001
        result = _clip_text(text)
        assert result.endswith("\n...[truncated]...")
        assert len(result) == 60000 + len("\n...[truncated]...")


# ---------------------------------------------------------------------------
# _normalize_timeout
# ---------------------------------------------------------------------------

class TestNormalizeTimeout:
    @pytest.mark.parametrize("val,expected", [
        (60, 60),
        (0, 120),       # <= 0 -> default
        (-5, 120),
        (5000, 3600),   # clamped to max
        (None, 120),
        ("abc", 120),
        ("200", 200),
        (3600, 3600),   # exactly max
    ])
    def test_values(self, val, expected):
        assert _normalize_timeout(val) == expected


# ---------------------------------------------------------------------------
# _normalize_retries
# ---------------------------------------------------------------------------

class TestNormalizeRetries:
    @pytest.mark.parametrize("val,expected", [
        (3, 3),
        (0, 1),
        (-1, 1),
        (100, 6),
        (None, 1),
        ("bad", 1),
        ("4", 4),
        (6, 6),
    ])
    def test_values(self, val, expected):
        assert _normalize_retries(val) == expected


# ---------------------------------------------------------------------------
# _normalize_bool
# ---------------------------------------------------------------------------

class TestNormalizeBool:
    @pytest.mark.parametrize("val,default,expected", [
        (None, True, True),
        (None, False, False),
        (True, False, True),
        (False, True, False),
        ("1", False, True),
        ("true", False, True),
        ("yes", False, True),
        ("on", False, True),
        ("0", True, False),
        ("false", True, False),
        ("no", True, False),
        ("off", True, False),
        ("maybe", True, True),
        ("maybe", False, False),
        ("TRUE", False, True),
        ("  Yes  ", False, True),
    ])
    def test_values(self, val, default, expected):
        assert _normalize_bool(val, default) == expected


# ---------------------------------------------------------------------------
# _normalize_packages
# ---------------------------------------------------------------------------

class TestNormalizePackages:
    def test_list_input(self):
        assert _normalize_packages(["numpy", "pandas"]) == ["numpy", "pandas"]

    def test_string_comma(self):
        assert _normalize_packages("numpy,pandas") == ["numpy", "pandas"]

    def test_string_space(self):
        assert _normalize_packages("numpy pandas") == ["numpy", "pandas"]

    def test_string_semicolon(self):
        assert _normalize_packages("numpy;pandas") == ["numpy", "pandas"]

    def test_dedup_case_insensitive(self):
        result = _normalize_packages(["NumPy", "numpy"])
        assert len(result) == 1
        assert result[0] == "NumPy"

    def test_rejects_bad_names(self):
        assert _normalize_packages(["good-pkg", "bad name!", "../evil"]) == ["good-pkg"]

    def test_max_cap(self):
        pkgs = [f"pkg{i}" for i in range(30)]
        assert len(_normalize_packages(pkgs)) == 24

    def test_none_input(self):
        assert _normalize_packages(None) == []

    def test_empty_string(self):
        assert _normalize_packages("") == []

    def test_empty_list(self):
        assert _normalize_packages([]) == []

    def test_chinese_separator(self):
        assert _normalize_packages("numpy，pandas；scipy") == ["numpy", "pandas", "scipy"]

    def test_skips_empty_items(self):
        assert _normalize_packages(["", None, "numpy"]) == ["numpy"]


# ---------------------------------------------------------------------------
# _extract_missing_module
# ---------------------------------------------------------------------------

class TestExtractMissingModule:
    def test_module_not_found(self):
        assert _extract_missing_module(
            "ModuleNotFoundError: No module named 'seaborn'"
        ) == "seaborn"

    def test_import_error(self):
        assert _extract_missing_module(
            "ImportError: No module named scipy.stats"
        ) == "scipy"

    def test_dotted_module(self):
        assert _extract_missing_module(
            "ModuleNotFoundError: No module named 'sklearn.ensemble'"
        ) == "sklearn"

    def test_none_input(self):
        assert _extract_missing_module(None) is None

    def test_empty_string(self):
        assert _extract_missing_module("") is None

    def test_no_match(self):
        assert _extract_missing_module("SyntaxError: invalid syntax") is None


# ---------------------------------------------------------------------------
# _venv_scope
# ---------------------------------------------------------------------------

class TestVenvScope:
    def test_empty_packages(self):
        assert _venv_scope([]) == "auto_default"

    def test_deterministic(self):
        a = _venv_scope(["numpy", "pandas"])
        b = _venv_scope(["numpy", "pandas"])
        assert a == b

    def test_order_independent(self):
        assert _venv_scope(["pandas", "numpy"]) == _venv_scope(["numpy", "pandas"])

    def test_case_independent(self):
        assert _venv_scope(["NumPy"]) == _venv_scope(["numpy"])

    def test_prefix(self):
        result = _venv_scope(["numpy"])
        assert result.startswith("pkg_")
        assert len(result) == 4 + 12  # "pkg_" + 12 hex chars


# ---------------------------------------------------------------------------
# _env_root / _env_python_path
# ---------------------------------------------------------------------------

class TestEnvPaths:
    def test_env_root(self):
        base = Path("/data/uploads")
        assert _env_root(base, "auto_default") == base / "chart_envs" / "auto_default"

    def test_env_python_unix(self, tmp_path):
        env_dir = tmp_path / "venv"
        unix_bin = env_dir / "bin" / "python"
        unix_bin.parent.mkdir(parents=True)
        unix_bin.touch()
        assert _env_python_path(env_dir) == unix_bin

    def test_env_python_windows_fallback(self, tmp_path):
        env_dir = tmp_path / "venv"
        env_dir.mkdir()
        # No bin/python -> falls back to Scripts/python.exe
        result = _env_python_path(env_dir)
        assert result == env_dir / "Scripts" / "python.exe"


# ---------------------------------------------------------------------------
# _build_runner_source
# ---------------------------------------------------------------------------

class TestBuildRunnerSource:
    def test_contains_user_code(self):
        src = _build_runner_source("print('hi')", None, Path("/out"), Path("/out/main.png"))
        assert "print('hi')" in src

    def test_sets_mpl_backend(self):
        src = _build_runner_source("pass", {}, Path("/o"), Path("/o/m.png"))
        assert "MPLBACKEND" in src
        assert "matplotlib.use('Agg')" in src

    def test_sets_mpl_config_dir_to_output(self):
        src = _build_runner_source("pass", {}, Path("/o"), Path("/o/m.png"))
        assert "MPLCONFIGDIR" in src
        assert ".mplconfig" in src

    def test_input_data_embedded(self):
        data = {"x": [1, 2, 3]}
        src = _build_runner_source("pass", data, Path("/o"), Path("/o/m.png"))
        # Data is double-JSON-encoded (json.dumps of a json string)
        assert "PAYLOAD_JSON" in src
        assert "INPUT_DATA = json.loads(PAYLOAD_JSON)" in src
        assert "x" in src and "1, 2, 3" in src

    def test_output_paths_embedded(self):
        src = _build_runner_source("pass", None, Path("/my/output"), Path("/my/output/chart.png"))
        assert "/my/output" in src
        assert "/my/output/chart.png" in src

    def test_valid_python_syntax(self):
        src = _build_runner_source("x = 1", {"a": 1}, Path("/o"), Path("/o/m.png"))
        compile(src, "<test>", "exec")  # should not raise


# ---------------------------------------------------------------------------
# resolve_chart_image_path (filesystem)
# ---------------------------------------------------------------------------

class TestResolveChartImagePath:
    def test_returns_existing_file(self, tmp_path):
        run_id = "chr_abc12345"
        chart_dir = tmp_path / "charts" / run_id
        chart_dir.mkdir(parents=True)
        img = chart_dir / "main.png"
        img.write_bytes(b"\x89PNG")
        result = resolve_chart_image_path(tmp_path, run_id, "main.png")
        assert result is not None
        assert result == img.resolve()

    def test_returns_none_missing_file(self, tmp_path):
        assert resolve_chart_image_path(tmp_path, "chr_abc12345", "nope.png") is None

    def test_rejects_bad_run_id(self, tmp_path):
        assert resolve_chart_image_path(tmp_path, "../../etc", "main.png") is None

    def test_rejects_bad_file_name(self, tmp_path):
        assert resolve_chart_image_path(tmp_path, "chr_abc12345", "../../etc/passwd") is None

    def test_rejects_none_inputs(self, tmp_path):
        assert resolve_chart_image_path(tmp_path, None, None) is None


# ---------------------------------------------------------------------------
# resolve_chart_run_meta_path (filesystem)
# ---------------------------------------------------------------------------

class TestResolveChartRunMetaPath:
    def test_returns_existing_meta(self, tmp_path):
        run_id = "chr_abc12345"
        run_dir = tmp_path / "chart_runs" / run_id
        run_dir.mkdir(parents=True)
        meta = run_dir / "meta.json"
        meta.write_text("{}", encoding="utf-8")
        result = resolve_chart_run_meta_path(tmp_path, run_id)
        assert result is not None
        assert result == meta.resolve()

    def test_returns_none_missing(self, tmp_path):
        assert resolve_chart_run_meta_path(tmp_path, "chr_abc12345") is None

    def test_rejects_bad_run_id(self, tmp_path):
        assert resolve_chart_run_meta_path(tmp_path, "../../../etc") is None

    def test_rejects_none(self, tmp_path):
        assert resolve_chart_run_meta_path(tmp_path, None) is None


# ---------------------------------------------------------------------------
# chart env lifecycle governance
# ---------------------------------------------------------------------------

class TestChartEnvLifecycle:
    def _policy(self, **overrides):
        policy = {
            "enabled": True,
            "ttl_sec": 3600,
            "min_keep": 1,
            "max_keep": 16,
            "max_total_bytes": 1 << 50,
            "active_grace_sec": 0,
            "lease_ttl_sec": 3600,
        }
        policy.update(overrides)
        return policy

    def _touch_env(self, root: Path, scope: str, mtime: float, payload: bytes = b"x") -> Path:
        env_dir = root / scope
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "payload.bin").write_bytes(payload)
        (env_dir / "bin").mkdir(exist_ok=True)
        (env_dir / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
        # set dir and file times so pruning can sort by age deterministically
        (env_dir / "payload.bin").touch()
        (env_dir / "bin" / "python").touch()
        import os
        os.utime(env_dir, (mtime, mtime))
        os.utime(env_dir / "payload.bin", (mtime, mtime))
        os.utime(env_dir / "bin" / "python", (mtime, mtime))
        return env_dir

    def test_mark_chart_env_used_writes_meta(self, tmp_path):
        uploads = tmp_path / "uploads"
        root = _chart_envs_root(uploads)
        env_dir = root / "pkg_meta"
        env_dir.mkdir(parents=True)

        _mark_chart_env_used(env_dir, scope="pkg_meta", packages=["numpy", "pandas"], now_ts=100.0)
        meta = json.loads((env_dir / ".env_meta.json").read_text(encoding="utf-8"))
        assert meta["scope"] == "pkg_meta"
        assert meta["packages"] == ["numpy", "pandas"]
        assert meta["last_used_ts"] == 100.0

    def test_prune_deletes_expired_env_but_keeps_current_scope(self, tmp_path):
        uploads = tmp_path / "uploads"
        root = _chart_envs_root(uploads)
        now_ts = 10_000.0
        self._touch_env(root, "pkg_old", mtime=now_ts - 8_000)
        self._touch_env(root, "pkg_keep", mtime=now_ts - 8_000)

        report = _prune_chart_envs(
            uploads,
            keep_scopes={"pkg_keep"},
            policy=self._policy(ttl_sec=3600, min_keep=1, max_keep=16, active_grace_sec=0),
            now_ts=now_ts,
        )
        assert (root / "pkg_old").exists() is False
        assert (root / "pkg_keep").exists() is True
        assert "pkg_old" in report["deleted_scopes"]
        assert "pkg_keep" not in report["deleted_scopes"]

    def test_prune_respects_max_keep_by_removing_oldest(self, tmp_path):
        uploads = tmp_path / "uploads"
        root = _chart_envs_root(uploads)
        now_ts = 20_000.0
        self._touch_env(root, "pkg_1", mtime=now_ts - 300)
        self._touch_env(root, "pkg_2", mtime=now_ts - 200)
        self._touch_env(root, "pkg_3", mtime=now_ts - 100)

        report = _prune_chart_envs(
            uploads,
            keep_scopes=set(),
            policy=self._policy(ttl_sec=999999, min_keep=1, max_keep=2, active_grace_sec=0),
            now_ts=now_ts,
        )
        assert (root / "pkg_1").exists() is False
        assert (root / "pkg_2").exists() is True
        assert (root / "pkg_3").exists() is True
        assert "pkg_1" in report["deleted_scopes"]

    def test_prune_skips_env_with_active_lease(self, tmp_path):
        uploads = tmp_path / "uploads"
        root = _chart_envs_root(uploads)
        now_ts = 30_000.0
        leased_dir = self._touch_env(root, "pkg_leased", mtime=now_ts - 600)
        self._touch_env(root, "pkg_free", mtime=now_ts - 500)
        (leased_dir / ".lease_run123").write_text("lease", encoding="utf-8")

        report = _prune_chart_envs(
            uploads,
            keep_scopes=set(),
            policy=self._policy(ttl_sec=999999, min_keep=1, max_keep=1, active_grace_sec=0, lease_ttl_sec=3600),
            now_ts=now_ts,
        )
        assert (root / "pkg_leased").exists() is True
        assert (root / "pkg_free").exists() is False
        assert "pkg_free" in report["deleted_scopes"]
        assert "pkg_leased" not in report["deleted_scopes"]
