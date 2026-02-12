"""Tests for teacher_memory_core facade and its underlying service modules.

Covers:
  - teacher_session_compaction_helpers (rate-limit, transcript, JSONL write)
  - teacher_session_compaction_service (threshold, disabled, compaction)
  - teacher_memory_search_service (empty query, keyword fallback, mem0 hit)
  - teacher_memory_propose_service (proposal creation, auto-apply, rejection)
  - teacher_memory_apply_service (approve, reject, already-processed)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so service imports resolve
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.api.teacher_session_compaction_helpers import (
    _teacher_compact_key,
    _teacher_compact_allowed,
    _teacher_compact_transcript,
    _write_teacher_session_records,
    reset_compact_state,
)
from services.api.teacher_session_compaction_service import (
    TeacherSessionCompactionDeps,
    maybe_compact_teacher_session,
)
from services.api.teacher_memory_search_service import (
    TeacherMemorySearchDeps,
    teacher_memory_search,
)
from services.api.teacher_memory_propose_service import (
    TeacherMemoryProposeDeps,
    teacher_memory_propose,
)
from services.api.teacher_memory_apply_service import (
    TeacherMemoryApplyDeps,
    teacher_memory_apply,
)


# ===================================================================
# Helpers
# ===================================================================

def _noop(*_a: Any, **_kw: Any) -> None:
    """No-op callable used as a stub for logging / side-effect deps."""


def _noop_dict(*_a: Any, **_kw: Any) -> Dict[str, Any]:
    return {}


# ===================================================================
# 1. Session compaction helpers
# ===================================================================

class TestTeacherCompactKey(unittest.TestCase):
    """_teacher_compact_key builds 'teacher_slug:session_slug' format."""

    def test_basic_format(self) -> None:
        key = _teacher_compact_key("teacher_abc123", "session_xyz789")
        self.assertIn(":", key)
        parts = key.split(":")
        self.assertEqual(len(parts), 2)
        self.assertTrue(len(parts[0]) >= 6)
        self.assertTrue(len(parts[1]) >= 6)

    def test_deterministic(self) -> None:
        a = _teacher_compact_key("t1_abcdef", "s1_abcdef")
        b = _teacher_compact_key("t1_abcdef", "s1_abcdef")
        self.assertEqual(a, b)


class TestTeacherCompactAllowed(unittest.TestCase):
    """Rate-limit: first call allowed, second within cooldown blocked."""

    def setUp(self) -> None:
        reset_compact_state()
        # Ensure interval is positive so rate-limiting is active
        import services.api.teacher_session_compaction_helpers as _helpers
        self._orig_interval = _helpers.TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC
        _helpers.TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC = 60

    def tearDown(self) -> None:
        import services.api.teacher_session_compaction_helpers as _helpers
        _helpers.TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC = self._orig_interval
        reset_compact_state()

    def test_first_call_allowed(self) -> None:
        self.assertTrue(_teacher_compact_allowed("teacher_aaaaaa", "session_bbbbbb"))

    def test_second_call_blocked(self) -> None:
        _teacher_compact_allowed("teacher_cccccc", "session_dddddd")
        self.assertFalse(_teacher_compact_allowed("teacher_cccccc", "session_dddddd"))

    def test_reset_clears_state(self) -> None:
        _teacher_compact_allowed("teacher_eeeeee", "session_ffffff")
        reset_compact_state()
        self.assertTrue(_teacher_compact_allowed("teacher_eeeeee", "session_ffffff"))


class TestTeacherCompactTranscript(unittest.TestCase):
    """Transcript builder respects roles and max_chars."""

    def test_builds_transcript(self) -> None:
        records = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "system", "content": "ignored"},
        ]
        text = _teacher_compact_transcript(records, max_chars=5000)
        self.assertIn("老师: Hello", text)
        self.assertIn("助理: Hi there", text)
        self.assertNotIn("ignored", text)

    def test_respects_max_chars(self) -> None:
        records = [{"role": "user", "content": "A" * 500}]
        text = _teacher_compact_transcript(records, max_chars=50)
        self.assertLessEqual(len(text), 60)  # small margin for tag prefix


class TestWriteTeacherSessionRecords(unittest.TestCase):
    """Atomic JSONL write to a temp file."""

    def test_writes_valid_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "session.jsonl"
            records = [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "world"},
            ]
            _write_teacher_session_records(p, records)
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["content"], "hello")
            self.assertEqual(json.loads(lines[1])["content"], "world")


# ===================================================================
# 2. Session compaction service
# ===================================================================

class TestMaybeCompactTeacherSession(unittest.TestCase):
    """Tests for maybe_compact_teacher_session with stubbed deps."""

    def _make_session_file(self, td: str, records: List[Dict[str, Any]]) -> Path:
        p = Path(td) / "session.jsonl"
        with p.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return p

    def _base_deps(self, **overrides: Any) -> TeacherSessionCompactionDeps:
        defaults = dict(
            compact_enabled=True,
            compact_main_only=False,
            compact_max_messages=5,
            compact_keep_tail=2,
            chat_max_messages_teacher=20,
            teacher_compact_allowed=lambda *_: True,
            teacher_session_file=lambda *_: Path("/nonexistent"),
            teacher_compact_summary=lambda recs, prev: "summary",
            write_teacher_session_records=lambda *_: None,
            mark_teacher_session_compacted=lambda *_: None,
            diag_log=_noop,
        )
        defaults.update(overrides)
        return TeacherSessionCompactionDeps(**defaults)

    def test_disabled_returns_reason(self) -> None:
        deps = self._base_deps(compact_enabled=False)
        result = maybe_compact_teacher_session("t1", "main", deps=deps)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "disabled")

    def test_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Only 3 dialog messages — below threshold of 5
            records = [
                {"role": "user", "content": f"msg{i}"} for i in range(3)
            ]
            p = self._make_session_file(td, records)
            deps = self._base_deps(teacher_session_file=lambda *_: p)
            result = maybe_compact_teacher_session("t1", "main", deps=deps)
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "below_threshold")

    def test_above_threshold_triggers_compaction(self) -> None:
        written: List[Any] = []
        marked: List[Any] = []

        with tempfile.TemporaryDirectory() as td:
            records = [
                {"role": "user", "content": f"msg{i}"} for i in range(10)
            ]
            p = self._make_session_file(td, records)
            deps = self._base_deps(
                teacher_session_file=lambda *_: p,
                write_teacher_session_records=lambda path, recs: written.append((path, recs)),
                mark_teacher_session_compacted=lambda *args: marked.append(args),
            )
            result = maybe_compact_teacher_session("t1", "main", deps=deps)
            self.assertTrue(result["ok"])
            self.assertGreater(result["compacted_messages"], 0)
            self.assertEqual(len(written), 1)
            self.assertEqual(len(marked), 1)


# ===================================================================
# 3. Memory search service
# ===================================================================

class TestTeacherMemorySearch(unittest.TestCase):
    """Tests for teacher_memory_search with stubbed deps."""

    def _base_deps(self, **overrides: Any) -> TeacherMemorySearchDeps:
        defaults = dict(
            ensure_teacher_workspace=_noop,
            mem0_search=lambda *_: {"ok": False},
            search_filter_expired=False,
            load_record=lambda *_: {},
            is_expired_record=lambda *_: False,
            diag_log=_noop,
            log_event=_noop,
            teacher_workspace_file=lambda tid, name: Path("/nonexistent") / name,
            teacher_daily_memory_dir=lambda tid: Path("/nonexistent/daily"),
        )
        defaults.update(overrides)
        return TeacherMemorySearchDeps(**defaults)

    def test_empty_query_returns_empty(self) -> None:
        deps = self._base_deps()
        result = teacher_memory_search("t1", "", deps=deps)
        self.assertEqual(result["matches"], [])

    def test_mem0_results_returned(self) -> None:
        mem0_matches = [{"id": "m1", "score": 0.9, "text": "hello"}]
        deps = self._base_deps(
            mem0_search=lambda *_: {"ok": True, "matches": mem0_matches},
        )
        result = teacher_memory_search("t1", "hello", deps=deps)
        self.assertEqual(result["mode"], "mem0")
        self.assertEqual(len(result["matches"]), 1)

    def test_keyword_fallback_when_mem0_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mem_file = Path(td) / "MEMORY.md"
            mem_file.write_text("line1\nfind_this_keyword\nline3\n", encoding="utf-8")

            def workspace_file(tid: str, name: str) -> Path:
                p = Path(td) / name
                if not p.exists():
                    p.touch()
                return p

            deps = self._base_deps(
                mem0_search=lambda *_: {"ok": True, "matches": []},
                teacher_workspace_file=workspace_file,
                teacher_daily_memory_dir=lambda tid: Path(td) / "daily",
            )
            result = teacher_memory_search("t1", "find_this_keyword", deps=deps)
            self.assertEqual(result["mode"], "keyword")
            self.assertGreaterEqual(len(result["matches"]), 1)
            self.assertIn("find_this_keyword", result["matches"][0]["snippet"])


# ===================================================================
# 4. Memory propose service
# ===================================================================

class TestTeacherMemoryPropose(unittest.TestCase):
    """Tests for teacher_memory_propose with stubbed deps."""

    def _base_deps(self, td: str, **overrides: Any) -> TeacherMemoryProposeDeps:
        proposals_dir = Path(td) / "proposals"
        proposals_dir.mkdir(exist_ok=True)

        def proposal_path(tid: str, pid: str) -> Path:
            return proposals_dir / f"{pid}.json"

        def atomic_write(path: Any, data: Any) -> None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        defaults = dict(
            ensure_teacher_workspace=_noop,
            proposal_path=proposal_path,
            atomic_write_json=atomic_write,
            uuid_hex=lambda: "aabbccddeeff00112233",
            now_iso=lambda: "2026-01-15T10:00:00",
            priority_score=lambda **kw: 50,
            record_ttl_days=lambda rec: 30,
            record_expire_at=lambda rec: None,
            auto_apply_enabled=False,
            auto_apply_targets={"MEMORY", "DAILY"},
            apply=lambda *_: {"ok": True, "status": "applied"},
        )
        defaults.update(overrides)
        return TeacherMemoryProposeDeps(**defaults)

    def test_creates_proposal_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            deps = self._base_deps(td)
            result = teacher_memory_propose(
                "t1", "MEMORY", "Test Title", "Test content",
                deps=deps, source="manual",
            )
            self.assertTrue(result["ok"])
            pid = result["proposal_id"]
            self.assertTrue(pid.startswith("tmem_"))
            # Verify file was written
            path = deps.proposal_path("t1", pid)
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["title"], "Test Title")
            self.assertEqual(record["content"], "Test content")
            self.assertEqual(record["status"], "proposed")

    def test_auto_apply_when_enabled_and_target_allowed(self) -> None:
        applied_calls: List[Any] = []

        def fake_apply(tid: str, pid: str, approve: bool) -> Dict[str, Any]:
            applied_calls.append((tid, pid, approve))
            return {"ok": True, "status": "applied"}

        with tempfile.TemporaryDirectory() as td:
            deps = self._base_deps(
                td,
                auto_apply_enabled=True,
                auto_apply_targets={"MEMORY", "DAILY"},
                apply=fake_apply,
            )
            result = teacher_memory_propose(
                "t1", "MEMORY", "Auto Title", "Auto content", deps=deps,
            )
            self.assertTrue(result["ok"])
            self.assertTrue(result.get("auto_applied"))
            self.assertEqual(len(applied_calls), 1)

    def test_auto_apply_rejected_when_target_not_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            deps = self._base_deps(
                td,
                auto_apply_enabled=True,
                auto_apply_targets={"MEMORY"},  # SOUL not in set
            )
            result = teacher_memory_propose(
                "t1", "SOUL", "Soul Title", "Soul content", deps=deps,
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "rejected")
            self.assertIn("target_not_allowed", result["error"])


# ===================================================================
# 5. Memory apply service
# ===================================================================

class TestTeacherMemoryApply(unittest.TestCase):
    """Tests for teacher_memory_apply with stubbed deps."""

    def _write_proposal(self, td: str, pid: str, record: Dict[str, Any]) -> Path:
        proposals_dir = Path(td) / "proposals"
        proposals_dir.mkdir(exist_ok=True)
        p = proposals_dir / f"{pid}.json"
        p.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return p

    def _base_deps(self, td: str, **overrides: Any) -> TeacherMemoryApplyDeps:
        proposals_dir = Path(td) / "proposals"
        proposals_dir.mkdir(exist_ok=True)
        output_dir = Path(td) / "workspace"
        output_dir.mkdir(exist_ok=True)

        def proposal_path(tid: str, pid: str) -> Path:
            return proposals_dir / f"{pid}.json"

        def atomic_write(path: Any, data: Any) -> None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        defaults = dict(
            proposal_path=proposal_path,
            atomic_write_json=atomic_write,
            now_iso=lambda: "2026-01-15T12:00:00",
            log_event=_noop,
            is_sensitive=lambda _: False,
            auto_apply_strict=False,
            teacher_daily_memory_path=lambda tid: output_dir / "daily.md",
            teacher_workspace_file=lambda tid, name: output_dir / name,
            find_conflicting_applied=lambda *_: [],
            record_ttl_days=lambda rec: 30,
            record_expire_at=lambda rec: None,
            is_expired_record=lambda rec: False,
            mark_superseded=_noop,
            diag_log=_noop,
            mem0_should_index_target=lambda _: False,
            mem0_index_entry=lambda *_: {"ok": True},
        )
        defaults.update(overrides)
        return TeacherMemoryApplyDeps(**defaults)

    def test_approve_writes_to_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pid = "tmem_test_approve"
            record = {
                "proposal_id": pid,
                "teacher_id": "t1",
                "target": "MEMORY",
                "title": "Approved Entry",
                "content": "This is approved content.",
                "source": "manual",
                "status": "proposed",
            }
            self._write_proposal(td, pid, record)
            deps = self._base_deps(td)
            result = teacher_memory_apply("t1", pid, deps=deps, approve=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "applied")
            # Verify content was appended to MEMORY.md
            out = Path(td) / "workspace" / "MEMORY.md"
            text = out.read_text(encoding="utf-8")
            self.assertIn("Approved Entry", text)
            self.assertIn("This is approved content.", text)

    def test_reject_marks_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pid = "tmem_test_reject"
            record = {
                "proposal_id": pid,
                "teacher_id": "t1",
                "target": "MEMORY",
                "title": "Rejected",
                "content": "content",
                "source": "manual",
                "status": "proposed",
            }
            self._write_proposal(td, pid, record)
            deps = self._base_deps(td)
            result = teacher_memory_apply("t1", pid, deps=deps, approve=False)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "rejected")
            # Verify proposal file updated
            path = deps.proposal_path("t1", pid)
            updated = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "rejected")

    def test_already_processed_returns_early(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pid = "tmem_test_already"
            record = {
                "proposal_id": pid,
                "teacher_id": "t1",
                "target": "MEMORY",
                "title": "Already Done",
                "content": "content",
                "source": "manual",
                "status": "applied",
                "applied_at": "2026-01-14T00:00:00",
            }
            self._write_proposal(td, pid, record)
            deps = self._base_deps(td)
            result = teacher_memory_apply("t1", pid, deps=deps, approve=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "applied")
            self.assertEqual(result["detail"], "already processed")


if __name__ == "__main__":
    unittest.main()
