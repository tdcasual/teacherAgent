from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from services.api import chart_executor as ce
from services.api import chart_sandbox, global_limits
from services.common.tool_registry import DEFAULT_TOOL_REGISTRY


class _AlwaysAcquireSemaphore:
    def acquire(self, timeout: float = 0.0) -> bool:
        return True

    def release(self) -> None:
        return None


def _patch_inner(monkeypatch: pytest.MonkeyPatch, observed: Dict[str, Any]) -> None:
    def _fake_inner(
        args: Dict[str, Any],
        app_root: Path,
        uploads_dir: Path,
        python_code: str,
        execution_profile: str,
    ) -> Dict[str, Any]:
        observed["execution_profile"] = execution_profile
        observed["args"] = dict(args)
        return {"ok": True, "execution_profile": execution_profile}

    monkeypatch.setattr(global_limits, "GLOBAL_CHART_EXEC_SEMAPHORE", _AlwaysAcquireSemaphore())
    monkeypatch.setattr(ce, "_execute_chart_exec_inner", _fake_inner)


def _enable_trusted(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sources: str = "operator_cli",
    roles: str = "admin",
) -> None:
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ENABLED", "1")
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", sources)
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", roles)


def test_chart_exec_schema_omits_execution_profile() -> None:
    tool = DEFAULT_TOOL_REGISTRY.require("chart.exec").to_openai()
    params = tool["function"]["parameters"]
    assert "execution_profile" not in (params.get("properties") or {})
    assert params.get("additionalProperties") is False


def test_chart_exec_schema_rejects_model_supplied_execution_profile() -> None:
    issues = DEFAULT_TOOL_REGISTRY.validate_arguments(
        "chart.exec",
        {"python_code": "print(1)", "execution_profile": "trusted"},
    )
    assert any("execution_profile" in item and "unexpected" in item for item in issues)


def test_trusted_not_enabled_denies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CHART_EXEC_TRUSTED_ENABLED", raising=False)
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", "operator_cli")
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", "admin")

    out = ce.execute_chart_exec(
        {
            "python_code": "print(1)",
            "execution_profile": "trusted",
            "_audit_source": "operator_cli",
            "_audit_role": "admin",
        },
        tmp_path,
        tmp_path / "uploads",
    )
    assert out["error"] == "chart_exec_trusted_forbidden"
    assert out["detail"] == "trusted_not_enabled"


def test_empty_allowlist_denies_even_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ENABLED", "1")
    monkeypatch.delenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", raising=False)
    monkeypatch.delenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", raising=False)

    out = ce.execute_chart_exec(
        {
            "python_code": "print(1)",
            "execution_profile": "trusted",
            "_audit_source": "operator_cli",
            "_audit_role": "admin",
        },
        tmp_path,
        tmp_path / "uploads",
    )
    assert out["error"] == "chart_exec_trusted_forbidden"
    assert out["detail"] == "trusted_allowlist_empty"


@pytest.mark.parametrize(
    ("sources", "roles"),
    [
        ("", "admin"),
        ("operator_cli", ""),
        ("operator_cli", "admin"),
    ],
)
def test_missing_one_allowlist_or_wrong_role_denies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sources: str,
    roles: str,
) -> None:
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ENABLED", "1")
    if sources:
        monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", sources)
    else:
        monkeypatch.delenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", raising=False)
    if roles:
        monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", roles)
    else:
        monkeypatch.delenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", raising=False)

    out = ce.execute_chart_exec(
        {
            "python_code": "print(1)",
            "execution_profile": "trusted",
            "_audit_source": "operator_cli",
            "_audit_role": "teacher",
        },
        tmp_path,
        tmp_path / "uploads",
    )
    assert out["error"] == "chart_exec_trusted_forbidden"
    if not sources or not roles:
        assert out["detail"] == "trusted_allowlist_empty"
    else:
        assert out["detail"] == "trusted_role_not_allowed"


@pytest.mark.parametrize("source", ["tool_loop", "chat", "llm"])
def test_llm_sources_denied_even_when_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    _enable_trusted(monkeypatch, sources=source, roles="admin")
    assert ce._trusted_policy_denial(role="admin", source=source) == "trusted_source_not_allowed"


def test_operator_trusted_allowed_when_enabled_and_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: Dict[str, Any] = {}
    _patch_inner(monkeypatch, observed)
    _enable_trusted(monkeypatch)

    out = ce.execute_chart_exec(
        {
            "python_code": "print(1)",
            "execution_profile": "trusted",
            "_audit_source": "operator_cli",
            "_audit_role": "admin",
        },
        tmp_path,
        tmp_path / "uploads",
    )
    assert out.get("ok") is True
    assert observed.get("execution_profile") == "trusted"


@pytest.mark.parametrize("source", ["tool_loop", "chat", "llm", "tool_dispatch.chart.exec"])
def test_llm_sources_force_sandboxed_and_ignore_trusted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: str,
) -> None:
    observed: Dict[str, Any] = {}
    _patch_inner(monkeypatch, observed)
    _enable_trusted(monkeypatch, sources=source, roles="teacher")

    out = ce.execute_chart_exec(
        {
            "python_code": "print(1)",
            "execution_profile": "trusted",
            "_audit_source": source,
            "_audit_role": "teacher",
        },
        tmp_path,
        tmp_path / "uploads",
    )
    assert out.get("ok") is True
    assert observed.get("execution_profile") == "sandboxed"


def test_exam_template_profile_is_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    observed: Dict[str, Any] = {}
    _patch_inner(monkeypatch, observed)

    out = ce.execute_chart_exec(
        {
            "python_code": "print(1)",
            "execution_profile": "template",
            "_audit_source": "exam.analysis.charts.generate",
            "_audit_role": "teacher",
        },
        tmp_path,
        tmp_path / "uploads",
    )
    assert out.get("ok") is True
    assert observed.get("execution_profile") == "template"


def test_all_profiles_are_scanned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    observed: Dict[str, Any] = {}
    _patch_inner(monkeypatch, observed)
    scanned: List[str] = []

    def _scan(code: str, profile: str) -> Optional[Dict[str, Any]]:
        scanned.append(profile)
        return None

    monkeypatch.setattr(chart_sandbox, "scan_code_patterns", _scan)
    _enable_trusted(monkeypatch)

    ce.execute_chart_exec(
        {"python_code": "print(1)", "execution_profile": "sandboxed"},
        tmp_path,
        tmp_path / "uploads",
    )
    ce.execute_chart_exec(
        {
            "python_code": "print(1)",
            "execution_profile": "template",
            "_audit_source": "exam.analysis.charts.generate",
        },
        tmp_path,
        tmp_path / "uploads",
    )
    ce.execute_chart_exec(
        {
            "python_code": "print(1)",
            "execution_profile": "trusted",
            "_audit_source": "operator_cli",
            "_audit_role": "admin",
        },
        tmp_path,
        tmp_path / "uploads",
    )
    assert scanned == ["sandboxed", "template", "trusted"]


def test_trusted_policy_denial_reasons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHART_EXEC_TRUSTED_ENABLED", raising=False)
    assert ce._trusted_policy_denial(role="admin", source="operator_cli") == "trusted_not_enabled"

    monkeypatch.setenv("CHART_EXEC_TRUSTED_ENABLED", "1")
    monkeypatch.delenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", raising=False)
    monkeypatch.delenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", raising=False)
    assert ce._trusted_policy_denial(role="admin", source="operator_cli") == "trusted_allowlist_empty"

    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_SOURCES", "operator_cli")
    monkeypatch.setenv("CHART_EXEC_TRUSTED_ALLOWED_ROLES", "admin")
    assert ce._trusted_policy_denial(role="admin", source="other") == "trusted_source_not_allowed"
    assert ce._trusted_policy_denial(role="teacher", source="operator_cli") == "trusted_role_not_allowed"
    assert ce._trusted_policy_denial(role="admin", source="operator_cli") is None
