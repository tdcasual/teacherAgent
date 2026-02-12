from __future__ import annotations

import builtins
import sys
import types

import pytest

from services.api import mem0_adapter as ma


@pytest.fixture(autouse=True)
def _reset_mem0_singleton_state():
    ma._MEM0_INSTANCE = None
    ma._MEM0_INIT_ERROR = None
    yield
    ma._MEM0_INSTANCE = None
    ma._MEM0_INIT_ERROR = None


def test_threshold_and_target_index_helpers(monkeypatch):
    monkeypatch.setenv("TEACHER_MEM0_THRESHOLD", "-1")
    assert ma.teacher_mem0_threshold_default() == 0.0

    monkeypatch.setenv("TEACHER_MEM0_THRESHOLD", "0.25")
    assert ma.teacher_mem0_threshold_default() == pytest.approx(0.25)

    monkeypatch.setenv("TEACHER_MEM0_INDEX_DAILY", "0")
    assert ma.teacher_mem0_index_daily_enabled() is False
    assert ma.teacher_mem0_should_index_target("DAILY") is False

    monkeypatch.setenv("TEACHER_MEM0_INDEX_DAILY", "1")
    assert ma.teacher_mem0_should_index_target("daily") is True
    assert ma.teacher_mem0_should_index_target("memory") is True
    assert ma.teacher_mem0_should_index_target("unknown") is False


def test_get_mem0_returns_cached_instance_when_available(monkeypatch):
    sentinel = object()

    fake_mem0 = types.ModuleType("mem0")

    class _Memory:
        @classmethod
        def from_config(cls, _config):
            return sentinel

    fake_mem0.Memory = _Memory

    fake_mem0_config = types.ModuleType("mem0_config")
    fake_mem0_config.get_config = lambda: {"provider": "fake"}

    monkeypatch.setitem(sys.modules, "mem0", fake_mem0)
    monkeypatch.setitem(sys.modules, "mem0_config", fake_mem0_config)

    first = ma.get_mem0()
    second = ma.get_mem0()

    assert first is sentinel
    assert second is sentinel


def test_get_mem0_import_failure_sets_init_error(monkeypatch):
    real_import = builtins.__import__

    def _failing_import(name, *args, **kwargs):
        if name == "mem0":
            raise RuntimeError("import failed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _failing_import)

    assert ma.get_mem0() is None
    assert ma._MEM0_INIT_ERROR == "import failed"
    assert ma.get_mem0() is None


def test_get_mem0_double_check_paths_inside_lock(monkeypatch):
    sentinel = object()

    class _LockSetInstance:
        def __enter__(self):
            ma._MEM0_INSTANCE = sentinel
            return self

        def __exit__(self, *_exc):
            return False

    monkeypatch.setattr(ma, "_MEM0_LOCK", _LockSetInstance())
    assert ma.get_mem0() is sentinel

    ma._MEM0_INSTANCE = None
    ma._MEM0_INIT_ERROR = None

    class _LockSetError:
        def __enter__(self):
            ma._MEM0_INIT_ERROR = "late-error"
            return self

        def __exit__(self, *_exc):
            return False

    monkeypatch.setattr(ma, "_MEM0_LOCK", _LockSetError())
    assert ma.get_mem0() is None


def test_chunk_text_handles_empty_short_and_long_inputs():
    assert ma._chunk_text("   ", max_chars=10, overlap_chars=2) == []
    assert ma._chunk_text("abc", max_chars=10, overlap_chars=2) == ["abc"]
    assert ma._chunk_text("abcdefghij", max_chars=4, overlap_chars=1) == ["abcd", "defg", "ghij"]


def test_teacher_mem0_search_returns_disabled_when_feature_off(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_enabled", lambda: False)
    result = ma.teacher_mem0_search("t1", "query")
    assert result == {"ok": False, "disabled": True, "matches": []}


def test_teacher_mem0_search_returns_error_when_mem0_unavailable(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_enabled", lambda: True)
    monkeypatch.setattr(ma, "get_mem0", lambda: None)
    ma._MEM0_INIT_ERROR = "init-error"

    result = ma.teacher_mem0_search("t1", "query")

    assert result == {"ok": False, "error": "init-error", "matches": []}


def test_teacher_mem0_search_handles_backend_exception(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_enabled", lambda: True)

    class _Memory:
        def search(self, *_args, **_kwargs):
            raise RuntimeError("search-failed")

    monkeypatch.setattr(ma, "get_mem0", lambda: _Memory())

    result = ma.teacher_mem0_search("teacher-x", "q")

    assert result["ok"] is False
    assert result["matches"] == []
    assert result["error"] == "search-failed"


def test_teacher_mem0_search_parses_dict_results_and_normalizes_metadata(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_enabled", lambda: True)

    calls = {}

    class _Memory:
        def search(self, query, *, user_id, limit, threshold, rerank):
            calls["args"] = (query, user_id, limit, threshold, rerank)
            return {
                "results": [
                    "skip-me",
                    {
                        "id": "m1",
                        "score": 0.9,
                        "memory": "x" * 500,
                        "created_at": "2026-01-01",
                        "metadata": {
                            "file": "f.md",
                            "title": "t",
                            "proposal_id": "p1",
                            "target": "MEMORY",
                        },
                    },
                    {
                        "id": "m2",
                        "score": 0.1,
                        "memory": "tiny",
                        "created_at": "2026-01-02",
                        "metadata": "not-a-dict",
                    },
                ]
            }

    monkeypatch.setattr(ma, "get_mem0", lambda: _Memory())

    result = ma.teacher_mem0_search("teacher-1", "find this", limit=3)

    assert calls["args"] == ("find this", "teacher:teacher-1", 3, 0.0, False)
    assert result["ok"] is True
    assert len(result["matches"]) == 2
    assert len(result["matches"][0]["snippet"]) == 400
    assert result["matches"][1]["file"] is None
    assert result["matches"][1]["target"] is None


def test_teacher_mem0_search_supports_list_response(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_enabled", lambda: True)

    class _Memory:
        def search(self, *_args, **_kwargs):
            return [{"id": "m1", "score": 0.5, "memory": "abc", "metadata": {}}]

    monkeypatch.setattr(ma, "get_mem0", lambda: _Memory())

    result = ma.teacher_mem0_search("teacher-1", "find", threshold=0.1)

    assert result == {
        "ok": True,
        "matches": [
            {
                "source": "mem0",
                "id": "m1",
                "score": 0.5,
                "snippet": "abc",
                "created_at": None,
                "file": None,
                "title": None,
                "proposal_id": None,
                "target": None,
            }
        ],
    }


def test_teacher_mem0_index_entry_returns_disabled_when_write_off(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_write_enabled", lambda: False)
    result = ma.teacher_mem0_index_entry("t1", "hello")
    assert result == {"ok": False, "disabled": True}


def test_teacher_mem0_index_entry_returns_error_when_mem0_unavailable(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_write_enabled", lambda: True)
    monkeypatch.setattr(ma, "get_mem0", lambda: None)
    ma._MEM0_INIT_ERROR = "no-mem0"

    result = ma.teacher_mem0_index_entry("t1", "hello")

    assert result == {"ok": False, "error": "no-mem0"}


def test_teacher_mem0_index_entry_rejects_empty_text_after_chunking(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_write_enabled", lambda: True)
    monkeypatch.setattr(ma, "get_mem0", lambda: object())
    monkeypatch.setattr(ma, "_chunk_text", lambda *_args, **_kwargs: [])

    result = ma.teacher_mem0_index_entry("t1", "   ")

    assert result == {"ok": False, "error": "empty_text"}


def test_teacher_mem0_index_entry_returns_progress_on_chunk_failure(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_write_enabled", lambda: True)
    monkeypatch.setattr(ma, "teacher_mem0_chunk_chars", lambda: 10)
    monkeypatch.setattr(ma, "teacher_mem0_chunk_overlap_chars", lambda: 2)
    monkeypatch.setattr(ma, "_chunk_text", lambda *_args, **_kwargs: ["c1", "c2"])

    calls = []

    class _Memory:
        def add(self, chunk, *, user_id, infer, metadata):
            calls.append((chunk, user_id, infer, metadata))
            if chunk == "c2":
                raise RuntimeError("add-failed")
            return {"id": "ok"}

    monkeypatch.setattr(ma, "get_mem0", lambda: _Memory())

    result = ma.teacher_mem0_index_entry("teacher-1", "payload", metadata={"target": "MEMORY"})

    assert calls[0][3]["chunk_index"] == 0
    assert calls[0][3]["chunk_total"] == 2
    assert result == {"ok": False, "error": "add-failed", "indexed": 1, "total": 2}


def test_teacher_mem0_index_entry_indexes_all_chunks(monkeypatch):
    monkeypatch.setattr(ma, "teacher_mem0_write_enabled", lambda: True)
    monkeypatch.setattr(ma, "teacher_mem0_chunk_chars", lambda: 10)
    monkeypatch.setattr(ma, "teacher_mem0_chunk_overlap_chars", lambda: 2)
    monkeypatch.setattr(ma, "_chunk_text", lambda *_args, **_kwargs: ["c1", "c2", "c3"])

    adds = []

    class _Memory:
        def add(self, chunk, *, user_id, infer, metadata):
            adds.append((chunk, user_id, infer, metadata))
            return {"id": chunk}

    monkeypatch.setattr(ma, "get_mem0", lambda: _Memory())

    result = ma.teacher_mem0_index_entry("teacher-9", "payload", metadata={"file": "f.md"})

    assert result == {"ok": True, "chunks": 3, "results_count": 3}
    assert adds[0][1] == "teacher:teacher-9"
    assert adds[0][2] is False
    assert adds[0][3]["file"] == "f.md"
    assert adds[2][3]["chunk_index"] == 2
    assert adds[2][3]["chunk_total"] == 3
