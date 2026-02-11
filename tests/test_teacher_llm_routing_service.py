"""Tests for services.api.teacher_llm_routing_service."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from services.api.teacher_llm_routing_service import (
    TeacherLlmRoutingDeps,
    _registry_for_actor,
    ensure_teacher_routing_file,
    routing_actor_from_teacher_id,
    teacher_llm_routing_apply,
    teacher_llm_routing_get,
    teacher_llm_routing_proposal_get,
    teacher_llm_routing_propose,
)

_DEFAULT_REG = {"openai": {"models": ["gpt-4o"]}}
_LLM = "services.api.llm_routing"
_SVC = "services.api.teacher_llm_routing_service"


def _make_deps(tmp_path: Path, **overrides) -> TeacherLlmRoutingDeps:
    defaults = dict(
        model_registry=_DEFAULT_REG,
        resolve_model_registry=lambda actor: {"merged": True},
        resolve_teacher_id=lambda tid: tid or "default-teacher",
        teacher_llm_routing_path=lambda actor: tmp_path / f"{actor}.json",
        legacy_routing_path=tmp_path / "legacy.json",
        atomic_write_json=lambda p, d: p.write_text(json.dumps(d), encoding="utf-8"),
        now_iso=lambda: "2026-02-11T00:00:00Z",
    )
    defaults.update(overrides)
    return TeacherLlmRoutingDeps(**defaults)


# ── _registry_for_actor ──────────────────────────────────────────────


class TestRegistryForActor:
    def test_resolve_succeeds(self, tmp_path: Path):
        deps = _make_deps(tmp_path, resolve_model_registry=lambda a: {"custom": True})
        assert _registry_for_actor("t1", deps=deps) == {"custom": True}

    def test_resolve_raises_falls_back(self, tmp_path: Path):
        deps = _make_deps(tmp_path, resolve_model_registry=lambda a: (_ for _ in ()).throw(RuntimeError("nope")))
        assert _registry_for_actor("t1", deps=deps) == _DEFAULT_REG

    def test_resolve_returns_non_dict_falls_back(self, tmp_path: Path):
        deps = _make_deps(tmp_path, resolve_model_registry=lambda a: "not-a-dict")
        assert _registry_for_actor("t1", deps=deps) == _DEFAULT_REG


# ── routing_actor_from_teacher_id ────────────────────────────────────


def test_routing_actor_delegates(tmp_path: Path):
    deps = _make_deps(tmp_path, resolve_teacher_id=lambda tid: f"resolved-{tid}")
    assert routing_actor_from_teacher_id("abc", deps=deps) == "resolved-abc"


# ── ensure_teacher_routing_file ──────────────────────────────────────


class TestEnsureTeacherRoutingFile:
    @patch(f"{_LLM}.ensure_routing_file")
    def test_legacy_migration(self, mock_ensure, tmp_path: Path):
        legacy = tmp_path / "legacy.json"
        legacy.write_text(json.dumps({"channels": []}), encoding="utf-8")
        deps = _make_deps(tmp_path)
        path = ensure_teacher_routing_file("actor1", deps=deps)
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["schema_version"] == 1
        assert written["updated_by"] == "actor1"
        mock_ensure.assert_called_once()

    @patch(f"{_LLM}.ensure_routing_file")
    def test_legacy_migration_failure_logged(self, mock_ensure, tmp_path: Path, caplog):
        legacy = tmp_path / "legacy.json"
        legacy.write_text("NOT-JSON", encoding="utf-8")
        deps = _make_deps(tmp_path)
        with caplog.at_level(logging.WARNING, logger="services.api.teacher_llm_routing_service"):
            ensure_teacher_routing_file("actor1", deps=deps)
        assert "legacy routing migration failed" in caplog.text


# ── teacher_llm_routing_get (_safe_int) ──────────────────────────────


@patch(f"{_LLM}.list_proposals", return_value=[])
@patch(
    f"{_LLM}.get_active_routing",
    return_value={"config": {}, "validation": {}, "history": list(range(50))},
)
@patch(f"{_LLM}.ensure_routing_file")
@patch(f"{_SVC}._provider_catalog_from_registry", return_value={})
def test_get_safe_int_non_numeric(mock_cat, mock_ens, mock_active, mock_prop, tmp_path: Path):
    deps = _make_deps(tmp_path)
    result = teacher_llm_routing_get(
        {"teacher_id": "t1", "history_limit": "not-a-number", "proposal_limit": "bad"},
        deps=deps,
    )
    assert result["ok"] is True
    # Non-numeric strings should fall back to default 20
    assert len(result["history"]) == 20


# ── teacher_llm_routing_propose ──────────────────────────────────────


def test_propose_missing_config(tmp_path: Path):
    deps = _make_deps(tmp_path)
    result = teacher_llm_routing_propose({"teacher_id": "t1"}, deps=deps)
    assert result == {"ok": False, "error": "config_required"}


# ── teacher_llm_routing_apply ────────────────────────────────────────


@patch(f"{_LLM}.ensure_routing_file")
def test_apply_missing_proposal_id(mock_ens, tmp_path: Path):
    deps = _make_deps(tmp_path)
    result = teacher_llm_routing_apply({"teacher_id": "t1"}, deps=deps)
    assert result == {"ok": False, "error": "proposal_id_required"}


# ── teacher_llm_routing_proposal_get ─────────────────────────────────


@patch(f"{_LLM}.ensure_routing_file")
def test_proposal_get_missing_id(mock_ens, tmp_path: Path):
    deps = _make_deps(tmp_path)
    result = teacher_llm_routing_proposal_get({"teacher_id": "t1"}, deps=deps)
    assert result == {"ok": False, "error": "proposal_id_required"}
