from __future__ import annotations

import json
import threading

from services.api import chat_idempotency_service as cis


def _safe_fs_id(value: str, prefix: str = "id") -> str:
    text = str(value or "").strip().replace("/", "_").replace(" ", "_")
    return text or f"{prefix}_empty"


def _deps(tmp_path, *, chat_job_exists=lambda _job_id: True, atomic_write_json=None):
    if atomic_write_json is None:
        def _write_json(path, payload):
            path.write_text(json.dumps(payload), encoding="utf-8")

        atomic_write_json = _write_json
    return cis.ChatIdempotencyDeps(
        request_map_dir=tmp_path / "request_map",
        request_index_path=tmp_path / "request_index.json",
        request_index_lock=threading.Lock(),
        safe_fs_id=_safe_fs_id,
        chat_job_exists=chat_job_exists,
        atomic_write_json=atomic_write_json,
    )


def test_load_chat_request_index_handles_corrupt_and_non_dict_payloads(tmp_path):
    path = tmp_path / "request_index.json"

    path.write_text("{bad", encoding="utf-8")
    assert cis.load_chat_request_index(path) == {}

    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert cis.load_chat_request_index(path) == {}


def test_request_map_get_handles_blank_read_failure_and_empty_content(tmp_path, monkeypatch):
    deps = _deps(tmp_path)

    assert cis.request_map_get("   ", deps) is None

    original_request_map_path = cis.request_map_path

    class _BadPath:
        def exists(self) -> bool:
            return True

        def read_text(self, **_kwargs):
            raise OSError("read failed")

    monkeypatch.setattr(cis, "request_map_path", lambda _request_id, _deps: _BadPath())
    assert cis.request_map_get("req-read-error", deps) is None

    monkeypatch.setattr(cis, "request_map_path", original_request_map_path)
    deps = _deps(tmp_path)
    path = cis.request_map_path("req-empty", deps)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("   ", encoding="utf-8")
    assert cis.request_map_get("req-empty", deps) is None


def test_request_map_get_keeps_entry_when_chat_job_exists_check_raises(tmp_path):
    def _raise_exists(_job_id: str) -> bool:
        raise RuntimeError("exists check failed")

    deps = _deps(tmp_path, chat_job_exists=_raise_exists)
    path = cis.request_map_path("req-1", deps)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("job-1", encoding="utf-8")

    assert cis.request_map_get("req-1", deps) == "job-1"


def test_request_map_set_if_absent_handles_blank_values_and_open_exception(tmp_path, monkeypatch):
    deps = _deps(tmp_path)

    assert cis.request_map_set_if_absent("", "job-1", deps) is False
    assert cis.request_map_set_if_absent("req-1", "", deps) is False

    monkeypatch.setattr(cis.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("open failed")))
    assert cis.request_map_set_if_absent("req-2", "job-2", deps) is False


def test_upsert_chat_request_index_swallows_atomic_write_failure(tmp_path):
    deps = _deps(tmp_path, atomic_write_json=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("write failed")))
    cis.upsert_chat_request_index("req-1", "job-1", deps)


def test_get_chat_job_id_by_request_prefers_request_map(monkeypatch, tmp_path):
    deps = _deps(tmp_path)
    monkeypatch.setattr(cis, "request_map_get", lambda _request_id, _deps: "job-direct")

    assert cis.get_chat_job_id_by_request("req-1", deps) == "job-direct"


def test_get_chat_job_id_by_request_handles_legacy_load_exception(monkeypatch, tmp_path):
    deps = _deps(tmp_path)
    monkeypatch.setattr(cis, "request_map_get", lambda _request_id, _deps: None)
    monkeypatch.setattr(cis, "load_chat_request_index", lambda _path: (_ for _ in ()).throw(RuntimeError("load failed")))

    assert cis.get_chat_job_id_by_request("req-1", deps) is None


def test_get_chat_job_id_by_request_handles_chat_job_exists_exception(monkeypatch, tmp_path):
    deps = _deps(tmp_path, chat_job_exists=lambda _job_id: (_ for _ in ()).throw(RuntimeError("exists failed")))
    deps.atomic_write_json(deps.request_index_path, {"req-1": "job-legacy"})
    monkeypatch.setattr(cis, "request_map_get", lambda _request_id, _deps: None)

    assert cis.get_chat_job_id_by_request("req-1", deps) is None


def test_get_chat_job_id_by_request_returns_none_when_legacy_job_missing(monkeypatch, tmp_path):
    deps = _deps(tmp_path, chat_job_exists=lambda _job_id: False)
    deps.atomic_write_json(deps.request_index_path, {"req-1": "job-legacy"})
    monkeypatch.setattr(cis, "request_map_get", lambda _request_id, _deps: None)

    assert cis.get_chat_job_id_by_request("req-1", deps) is None
