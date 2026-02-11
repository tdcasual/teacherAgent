"""Tests for services.api.llm_routing_proposals."""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

import services.api.llm_routing as llm_routing_mod
import services.api.llm_routing_proposals as mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_TS = "2026-01-15T12:00:00Z"
FIXED_ID = "proposal_test_001"


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def _dummy_lock():
    lock = threading.RLock()
    yield lock


def _patch_lr(monkeypatch, **overrides):
    """Patch llm_routing helpers used by the proposals module."""
    defaults = {
        "_safe_id": lambda prefix="": FIXED_ID,
        "_now_iso": lambda: FIXED_TS,
        "_atomic_write_json": lambda p, d: _write_json(p, d),
        "_read_json": _read_json,
        "_config_lock": lambda cp: threading.RLock(),
    }
    defaults.update(overrides)
    for attr, val in defaults.items():
        monkeypatch.setattr(llm_routing_mod, attr, val)


# ---------------------------------------------------------------------------
# _as_str
# ---------------------------------------------------------------------------

class TestAsStr:
    @pytest.mark.parametrize("inp,expected", [
        (None, ""),
        ("", ""),
        ("  hello  ", "hello"),
        (42, "42"),
        (0, "0"),
        (True, "True"),
    ])
    def test_basic(self, inp, expected):
        assert mod._as_str(inp) == expected


# ---------------------------------------------------------------------------
# create_routing_proposal
# ---------------------------------------------------------------------------

class TestCreateRoutingProposal:
    def test_ok(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        normalized = {"schema_version": 1, "enabled": True}
        monkeypatch.setattr(llm_routing_mod, "validate_routing_config",
                            lambda payload, reg: {"ok": True, "normalized": normalized, "errors": [], "warnings": []})
        _patch_lr(monkeypatch)

        res = mod.create_routing_proposal(cfg, {}, {"enabled": True}, "alice", "my note")
        assert res["ok"] is True
        assert res["proposal_id"] == FIXED_ID
        assert res["status"] == "pending"
        assert res["validation"]["ok"] is True
        # file written
        written = _read_json(Path(res["proposal_path"]))
        assert written["created_by"] == "alice"
        assert written["candidate"] == normalized

    def test_validation_fail_stores_raw_payload(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        raw = {"bad": "config"}
        monkeypatch.setattr(llm_routing_mod, "validate_routing_config",
                            lambda p, r: {"ok": False, "normalized": None, "errors": ["bad"], "warnings": []})
        _patch_lr(monkeypatch)

        res = mod.create_routing_proposal(cfg, {}, raw, "", "")
        assert res["ok"] is True  # proposal created even if validation fails
        assert res["validation"]["ok"] is False
        written = _read_json(Path(res["proposal_path"]))
        assert written["candidate"] == raw
        assert written["created_by"] == "unknown"  # empty actor → "unknown"


# ---------------------------------------------------------------------------
# read_proposal
# ---------------------------------------------------------------------------

class TestReadProposal:
    def test_found(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        pdir = tmp_path / "llm_routing_proposals"
        pdir.mkdir()
        _write_json(pdir / "p1.json", {"proposal_id": "p1", "status": "pending"})
        _patch_lr(monkeypatch)

        res = mod.read_proposal(cfg, "p1")
        assert res["ok"] is True
        assert res["proposal"]["proposal_id"] == "p1"

    def test_not_found(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        _patch_lr(monkeypatch)
        res = mod.read_proposal(cfg, "nope")
        assert res["ok"] is False
        assert res["error"] == "proposal_not_found"


# ---------------------------------------------------------------------------
# list_proposals
# ---------------------------------------------------------------------------

class TestListProposals:
    def _seed(self, tmp_path, items):
        pdir = tmp_path / "llm_routing_proposals"
        pdir.mkdir(exist_ok=True)
        for item in items:
            _write_json(pdir / f"{item['proposal_id']}.json", item)

    def test_empty_dir_missing(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        _patch_lr(monkeypatch)
        assert mod.list_proposals(cfg) == []

    def test_returns_sorted_by_created_at(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        self._seed(tmp_path, [
            {"proposal_id": "a", "created_at": "2026-01-01", "status": "pending", "validation": {"ok": True}},
            {"proposal_id": "b", "created_at": "2026-01-03", "status": "applied", "validation": {"ok": True}},
            {"proposal_id": "c", "created_at": "2026-01-02", "status": "pending", "validation": {"ok": False}},
        ])
        _patch_lr(monkeypatch)
        items = mod.list_proposals(cfg)
        assert [i["proposal_id"] for i in items] == ["b", "c", "a"]

    def test_filter_by_status(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        self._seed(tmp_path, [
            {"proposal_id": "a", "created_at": "2026-01-01", "status": "pending", "validation": {"ok": True}},
            {"proposal_id": "b", "created_at": "2026-01-02", "status": "applied", "validation": {"ok": True}},
        ])
        _patch_lr(monkeypatch)
        items = mod.list_proposals(cfg, status="pending")
        assert len(items) == 1
        assert items[0]["proposal_id"] == "a"

    def test_limit(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        self._seed(tmp_path, [
            {"proposal_id": f"p{i}", "created_at": f"2026-01-{i:02d}", "status": "pending", "validation": {"ok": True}}
            for i in range(1, 6)
        ])
        _patch_lr(monkeypatch)
        assert len(mod.list_proposals(cfg, limit=2)) == 2


# ---------------------------------------------------------------------------
# apply_routing_proposal
# ---------------------------------------------------------------------------

class TestApplyRoutingProposal:
    def _seed_proposal(self, tmp_path, pid="p1", status="pending", candidate=None):
        pdir = tmp_path / "llm_routing_proposals"
        pdir.mkdir(exist_ok=True)
        data = {"proposal_id": pid, "status": status, "candidate": candidate or {"enabled": True}, "note": "n"}
        _write_json(pdir / f"{pid}.json", data)

    def test_empty_proposal_id(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        _patch_lr(monkeypatch)
        res = mod.apply_routing_proposal(cfg, {}, "", True, "bob")
        assert res == {"ok": False, "error": "proposal_id_required"}

    def test_none_proposal_id(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        _patch_lr(monkeypatch)
        res = mod.apply_routing_proposal(cfg, {}, None, True, "bob")
        assert res == {"ok": False, "error": "proposal_id_required"}

    def test_not_found(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        _patch_lr(monkeypatch)
        res = mod.apply_routing_proposal(cfg, {}, "missing", True, "bob")
        assert res["ok"] is False
        assert res["error"] == "proposal_not_found"

    def test_already_applied(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        self._seed_proposal(tmp_path, status="applied")
        _patch_lr(monkeypatch)
        res = mod.apply_routing_proposal(cfg, {}, "p1", True, "bob")
        assert res["error"] == "proposal_already_reviewed"

    def test_already_rejected(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        self._seed_proposal(tmp_path, status="rejected")
        _patch_lr(monkeypatch)
        res = mod.apply_routing_proposal(cfg, {}, "p1", True, "bob")
        assert res["error"] == "proposal_already_reviewed"

    def test_reject(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        self._seed_proposal(tmp_path)
        _patch_lr(monkeypatch)
        res = mod.apply_routing_proposal(cfg, {}, "p1", False, "bob")
        assert res == {"ok": True, "proposal_id": "p1", "status": "rejected"}
        saved = _read_json(tmp_path / "llm_routing_proposals" / "p1.json")
        assert saved["status"] == "rejected"
        assert saved["reviewed_by"] == "bob"
        assert saved["reviewed_at"] == FIXED_TS

    def test_approve_success(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        self._seed_proposal(tmp_path)
        _patch_lr(monkeypatch)
        monkeypatch.setattr(llm_routing_mod, "apply_routing_config",
                            lambda **kw: {"ok": True, "version": "v7", "history_path": "/tmp/h"})
        res = mod.apply_routing_proposal(cfg, {}, "p1", True, "bob")
        assert res["ok"] is True
        assert res["status"] == "applied"
        assert res["version"] == "v7"
        saved = _read_json(tmp_path / "llm_routing_proposals" / "p1.json")
        assert saved["status"] == "applied"
        assert saved["applied_version"] == "v7"

    def test_approve_apply_fails(self, tmp_path, monkeypatch):
        cfg = tmp_path / "routing.json"
        self._seed_proposal(tmp_path)
        _patch_lr(monkeypatch)
        monkeypatch.setattr(llm_routing_mod, "apply_routing_config",
                            lambda **kw: {"ok": False, "error": "boom"})
        res = mod.apply_routing_proposal(cfg, {}, "p1", True, "bob")
        assert res["ok"] is False
        assert res["status"] == "failed"
        saved = _read_json(tmp_path / "llm_routing_proposals" / "p1.json")
        assert saved["status"] == "failed"
        assert saved["apply_error"]["error"] == "boom"

    def test_approve_non_dict_candidate(self, tmp_path, monkeypatch):
        """When candidate is not a dict, apply receives empty dict."""
        pdir = tmp_path / "llm_routing_proposals"
        pdir.mkdir(exist_ok=True)
        _write_json(pdir / "p2.json", {"proposal_id": "p2", "status": "pending", "candidate": "bad", "note": ""})
        cfg = tmp_path / "routing.json"
        _patch_lr(monkeypatch)
        captured = {}
        def fake_apply(**kw):
            captured.update(kw)
            return {"ok": True, "version": "v1", "history_path": "/h"}
        monkeypatch.setattr(llm_routing_mod, "apply_routing_config", fake_apply)
        res = mod.apply_routing_proposal(cfg, {}, "p2", True, "bob")
        assert res["ok"] is True
        assert captured["config_payload"] == {}
