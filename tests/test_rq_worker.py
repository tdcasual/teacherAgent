from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, List

import pytest

from services.api.workers import rq_worker


def _service_block(compose_text: str, service_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^  {re.escape(service_name)}:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|^volumes:\n|\Z)"
    )
    match = pattern.search(compose_text)
    assert match is not None, f"service not found: {service_name}"
    return match.group("body")


def test_compose_worker_healthcheck_is_heartbeat() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    worker = _service_block(text, "worker")
    assert "stat -c %Y /tmp/rq_worker_heartbeat" in worker
    assert "-lt 30" in worker
    assert "pgrep -f 'rq worker'" not in worker
    assert re.search(r"pgrep\s+-f\s+'services\.api\.workers\.rq_worker'", worker) is None
    assert re.search(r'pgrep\s+-f\s+"services\.api\.workers\.rq_worker"', worker) is None
    assert re.search(r"pgrep\s+-f\s+services\.api\.workers\.rq_worker", worker) is None


def test_compose_scan_pending_defaults_on() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    worker = _service_block(text, "worker")
    assert "RQ_SCAN_PENDING_ON_START=${RQ_SCAN_PENDING_ON_START:-1}" in worker
    assert "RQ_SCAN_PENDING_ON_START=${RQ_SCAN_PENDING_ON_START:-0}" not in worker


def test_coverage_no_longer_omits_rq_worker() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "services/api/workers/rq_worker.py" not in text


def test_rq_worker_main_scans_when_env_truthy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scanned: List[tuple[str, str | None]] = []
    heartbeat = tmp_path / "rq_worker_heartbeat"
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    monkeypatch.setenv("RQ_SCAN_PENDING_ON_START", "1")
    monkeypatch.setenv("RQ_HEARTBEAT_PATH", str(heartbeat))
    monkeypatch.setenv("TENANT_ID", "tenant-a")
    monkeypatch.setenv("RQ_QUEUE_NAME", "jobs")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    monkeypatch.setattr(
        rq_worker,
        "scan_pending_upload_jobs",
        lambda tenant_id=None: scanned.append(("upload", tenant_id)),
    )
    monkeypatch.setattr(
        rq_worker,
        "scan_pending_exam_jobs",
        lambda tenant_id=None: scanned.append(("exam", tenant_id)),
    )
    monkeypatch.setattr(
        rq_worker,
        "scan_pending_chat_jobs",
        lambda tenant_id=None: scanned.append(("chat", tenant_id)),
    )
    monkeypatch.setattr(rq_worker, "get_redis_client", lambda _url, decode_responses: {"redis": True})

    created: List[Any] = []

    class _Worker:
        def __init__(self, queues: List[str], connection: Any) -> None:
            self.queues = queues
            self.connection = connection
            created.append(self)

        def work(self) -> None:
            self.worked = True

    started: List[Any] = []

    class _Thread:
        def __init__(self, target: Any, args: tuple[Any, ...] = (), name: str | None = None, daemon: bool | None = None) -> None:
            self.target = target
            self.args = args
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            started.append(self)

    monkeypatch.setattr(rq_worker, "Worker", _Worker)
    monkeypatch.setattr(rq_worker.threading, "Thread", _Thread)

    rq_worker.main()

    assert scanned == [("upload", "tenant-a"), ("exam", "tenant-a"), ("chat", "tenant-a")]
    assert heartbeat.is_file()
    assert started and started[0].daemon is True
    assert created[0].queues == ["jobs"]
    assert created[0].worked is True
    assert os.getenv("JOB_QUEUE_BACKEND") == "rq"


def test_rq_worker_main_skips_scan_when_env_falsy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scanned: List[str] = []
    heartbeat = tmp_path / "nested" / "hb"
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    monkeypatch.setenv("RQ_SCAN_PENDING_ON_START", "0")
    monkeypatch.setenv("RQ_HEARTBEAT_PATH", str(heartbeat))
    monkeypatch.delenv("TENANT_ID", raising=False)
    monkeypatch.delenv("RQ_QUEUE_NAME", raising=False)

    monkeypatch.setattr(rq_worker, "scan_pending_upload_jobs", lambda tenant_id=None: scanned.append("upload"))
    monkeypatch.setattr(rq_worker, "scan_pending_exam_jobs", lambda tenant_id=None: scanned.append("exam"))
    monkeypatch.setattr(rq_worker, "scan_pending_chat_jobs", lambda tenant_id=None: scanned.append("chat"))
    monkeypatch.setattr(rq_worker, "get_redis_client", lambda _url, decode_responses: "conn")

    class _Worker:
        def __init__(self, queues: List[str], connection: Any) -> None:
            self.queues = queues
            self.connection = connection

        def work(self) -> None:
            return None

    class _Thread:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def start(self) -> None:
            return None

    monkeypatch.setattr(rq_worker, "Worker", _Worker)
    monkeypatch.setattr(rq_worker.threading, "Thread", _Thread)

    rq_worker.main()

    assert scanned == []
    assert heartbeat.is_file()


def test_heartbeat_loop_refreshes_mtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "hb"
    path.write_text("x", encoding="utf-8")
    os.utime(path, (0, 0))
    calls = {"n": 0}

    def _sleep(_seconds: float) -> None:
        calls["n"] += 1
        if calls["n"] >= 2:
            raise KeyboardInterrupt()

    monkeypatch.setattr(rq_worker.time, "sleep", _sleep)
    with pytest.raises(KeyboardInterrupt):
        rq_worker._heartbeat_loop(str(path), 10)
    assert path.stat().st_mtime > 0


def test_refresh_heartbeat_recreates_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "hb"
    rq_worker._refresh_heartbeat(str(path))
    assert path.is_file()


def test_truthy_values() -> None:
    assert rq_worker._truthy("1") is True
    assert rq_worker._truthy("true") is True
    assert rq_worker._truthy("YES") is True
    assert rq_worker._truthy("on") is True
    assert rq_worker._truthy("0") is False
    assert rq_worker._truthy("") is False
    assert rq_worker._truthy(None) is False  # type: ignore[arg-type]
