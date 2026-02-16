from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

_log = logging.getLogger(__name__)
CHAT_STREAM_EVENT_VERSION = 1
CHAT_STREAM_SIGNAL_TTL_SEC = 1800.0
CHAT_STREAM_SIGNAL_MAX_ENTRIES = 4096
CHAT_STREAM_SIGNAL_SWEEP_INTERVAL_SEC = 0.5


class _StreamSignal:
    def __init__(self) -> None:
        self.cond = threading.Condition()
        self.version = 0
        self.last_touched = time.monotonic()

    def touch(self, now: float | None = None) -> None:
        self.last_touched = float(now if now is not None else time.monotonic())


_STREAM_SIGNAL_LOCK = threading.Lock()
_STREAM_SIGNALS: Dict[str, _StreamSignal] = {}
_STREAM_SIGNAL_LAST_SWEEP_TS = 0.0


def _job_signal_key(job_id: str) -> str:
    return str(job_id or "").strip() or "_"


def _trim_signal_capacity_locked() -> None:
    cap = max(1, int(CHAT_STREAM_SIGNAL_MAX_ENTRIES))
    while len(_STREAM_SIGNALS) > cap:
        oldest_key = ""
        oldest_ts = float("inf")
        for key, signal in _STREAM_SIGNALS.items():
            if signal.last_touched < oldest_ts:
                oldest_key = key
                oldest_ts = signal.last_touched
        if not oldest_key:
            break
        _STREAM_SIGNALS.pop(oldest_key, None)


def _evict_stream_signals_locked(now: float) -> None:
    global _STREAM_SIGNAL_LAST_SWEEP_TS
    ttl = max(1.0, float(CHAT_STREAM_SIGNAL_TTL_SEC))
    stale_keys = [key for key, signal in _STREAM_SIGNALS.items() if (now - signal.last_touched) >= ttl]
    for key in stale_keys:
        _STREAM_SIGNALS.pop(key, None)
    _trim_signal_capacity_locked()
    _STREAM_SIGNAL_LAST_SWEEP_TS = now


def _signal_for_job(job_id: str) -> _StreamSignal:
    key = _job_signal_key(job_id)
    with _STREAM_SIGNAL_LOCK:
        now = time.monotonic()
        sweep_interval = max(0.05, float(CHAT_STREAM_SIGNAL_SWEEP_INTERVAL_SEC))
        cap = max(1, int(CHAT_STREAM_SIGNAL_MAX_ENTRIES))
        should_sweep = (now - _STREAM_SIGNAL_LAST_SWEEP_TS) >= sweep_interval
        if should_sweep or len(_STREAM_SIGNALS) > cap:
            _evict_stream_signals_locked(now)
        signal = _STREAM_SIGNALS.get(key)
        if signal is None:
            signal = _StreamSignal()
            _STREAM_SIGNALS[key] = signal
        signal.touch(now)
        _trim_signal_capacity_locked()
        return signal


def clear_chat_stream_signal(job_id: str) -> None:
    key = _job_signal_key(job_id)
    with _STREAM_SIGNAL_LOCK:
        _STREAM_SIGNALS.pop(key, None)


def notify_chat_stream_event(job_id: str) -> None:
    signal = _signal_for_job(job_id)
    with signal.cond:
        signal.version += 1
        signal.touch()
        signal.cond.notify_all()


def wait_for_chat_stream_event(job_id: str, last_seen_version: int, timeout_sec: float = 1.0) -> int:
    signal = _signal_for_job(job_id)
    seen = max(0, _coerce_int(last_seen_version, 0))
    timeout = max(0.0, float(timeout_sec or 0.0))
    with signal.cond:
        if signal.version > seen:
            signal.touch()
            return signal.version
        signal.cond.wait(timeout=timeout)
        signal.touch()
        return signal.version


@dataclass(frozen=True)
class ChatEventStreamDeps:
    chat_job_path: Callable[[str], Path]
    chat_job_lock: Any
    now_iso: Callable[[], str]
    notify_job_event: Callable[[str], None] | None = None
    wait_job_event: Callable[[str, int, float], int] | None = None


def chat_event_log_path(job_id: str, *, deps: ChatEventStreamDeps) -> Path:
    return deps.chat_job_path(job_id) / "events.jsonl"


def _chat_event_seq_path(job_id: str, *, deps: ChatEventStreamDeps) -> Path:
    return deps.chat_job_path(job_id) / "events.seq"


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _load_max_event_id_from_log(path: Path) -> int:
    if not path.exists():
        return 0
    max_id = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = str(line or "").strip()
                if not text:
                    continue
                try:
                    item = json.loads(text)
                except Exception:
                    _log.debug("JSON parse failed", exc_info=True)
                    continue
                if not isinstance(item, dict):
                    continue
                event_id = _coerce_int(item.get("event_id"), 0)
                if event_id > max_id:
                    max_id = event_id
    except Exception:
        _log.warning("failed to scan chat event log: %s", path, exc_info=True)
        return 0
    return max_id


def _read_current_event_id(job_id: str, *, deps: ChatEventStreamDeps) -> int:
    seq_path = _chat_event_seq_path(job_id, deps=deps)
    if seq_path.exists():
        try:
            return _coerce_int(seq_path.read_text(encoding="utf-8").strip(), 0)
        except Exception:
            _log.debug("operation failed", exc_info=True)
    return _load_max_event_id_from_log(chat_event_log_path(job_id, deps=deps))


def append_chat_event(
    job_id: str,
    event_type: str,
    payload: Dict[str, Any],
    *,
    deps: ChatEventStreamDeps,
) -> Dict[str, Any]:
    event_name = str(event_type or "").strip()
    if not event_name:
        raise ValueError("event_type is required")
    job_dir = deps.chat_job_path(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    log_path = chat_event_log_path(job_id, deps=deps)
    seq_path = _chat_event_seq_path(job_id, deps=deps)
    lock = deps.chat_job_lock if deps.chat_job_lock is not None else nullcontext()
    with lock:
        current_id = _read_current_event_id(job_id, deps=deps)
        next_id = current_id + 1
        event = {
            "event_id": next_id,
            "event_version": CHAT_STREAM_EVENT_VERSION,
            "type": event_name,
            "payload": payload if isinstance(payload, dict) else {},
            "ts": deps.now_iso(),
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        try:
            seq_path.write_text(str(next_id), encoding="utf-8")
        except Exception:
            _log.debug("operation failed", exc_info=True)
        try:
            if callable(deps.notify_job_event):
                deps.notify_job_event(job_id)
        except Exception:
            _log.debug("operation failed", exc_info=True)
        if event_name in {"job.done", "job.failed", "job.cancelled"}:
            clear_chat_stream_signal(job_id)
        return event


def load_chat_events(
    job_id: str,
    *,
    deps: ChatEventStreamDeps,
    after_event_id: int = 0,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    path = chat_event_log_path(job_id, deps=deps)
    if not path.exists():
        return []
    after = max(0, _coerce_int(after_event_id, 0))
    cap = max(1, min(_coerce_int(limit, 200), 1000))
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = str(line or "").strip()
                if not text:
                    continue
                try:
                    item = json.loads(text)
                except Exception:
                    _log.debug("JSON parse failed", exc_info=True)
                    continue
                if not isinstance(item, dict):
                    continue
                event_id = _coerce_int(item.get("event_id"), 0)
                if event_id <= after:
                    continue
                out.append(item)
                if len(out) >= cap:
                    break
    except Exception:
        _log.warning("failed to load chat events for job=%s", job_id, exc_info=True)
        return []
    return out


def load_chat_events_incremental(
    job_id: str,
    *,
    deps: ChatEventStreamDeps,
    after_event_id: int = 0,
    offset_hint: int | None = None,
    limit: int = 200,
) -> tuple[List[Dict[str, Any]], int]:
    path = chat_event_log_path(job_id, deps=deps)
    hint = _coerce_int(offset_hint, 0) if offset_hint is not None else None
    if not path.exists():
        return [], max(0, int(hint or 0))
    after = max(0, _coerce_int(after_event_id, 0))
    cap = max(1, min(_coerce_int(limit, 200), 1000))
    out: List[Dict[str, Any]] = []
    next_offset = max(0, int(hint or 0))
    try:
        with path.open("r", encoding="utf-8") as handle:
            use_hint = hint is not None
            if use_hint:
                try:
                    size = path.stat().st_size
                except Exception:
                    size = 0
                if hint is None or hint < 0 or hint > size:
                    use_hint = False
            if use_hint and hint is not None:
                handle.seek(hint)
            else:
                handle.seek(0)
            while True:
                line = handle.readline()
                if line == "":
                    break
                text = str(line or "").strip()
                if not text:
                    continue
                try:
                    item = json.loads(text)
                except Exception:
                    _log.debug("JSON parse failed", exc_info=True)
                    continue
                if not isinstance(item, dict):
                    continue
                event_id = _coerce_int(item.get("event_id"), 0)
                if event_id <= after:
                    continue
                out.append(item)
                if len(out) >= cap:
                    break
            next_offset = max(0, _coerce_int(handle.tell(), 0))
    except Exception:
        _log.warning("failed to load incremental chat events for job=%s", job_id, exc_info=True)
        return [], max(0, int(hint or 0))
    return out, next_offset


def encode_sse_event(event: Dict[str, Any]) -> str:
    item = event if isinstance(event, dict) else {}
    event_id = _coerce_int(item.get("event_id"), 0)
    event_version = _coerce_int(item.get("event_version"), CHAT_STREAM_EVENT_VERSION)
    if event_version <= 0:
        event_version = CHAT_STREAM_EVENT_VERSION
    event_type = str(item.get("type") or "message")
    payload = item.get("payload")
    data = {
        "event_id": event_id,
        "event_version": event_version,
        "type": event_type,
        "payload": payload,
    }
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )
