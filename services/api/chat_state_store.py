from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Set, Tuple


@dataclass
class ChatStateStore:
    chat_job_lock: threading.Lock
    chat_job_event: threading.Event
    worker_started: bool
    lane_cursor: int
    chat_job_lanes: Dict[str, Deque[str]] = field(default_factory=dict)
    chat_job_active_lanes: Set[str] = field(default_factory=set)
    chat_job_queued: Set[str] = field(default_factory=set)
    chat_job_to_lane: Dict[str, str] = field(default_factory=dict)
    chat_lane_recent: Dict[str, Tuple[float, str, str]] = field(default_factory=dict)
    chat_worker_threads: List[threading.Thread] = field(default_factory=list)


@dataclass
class ChatIdempotencyStore:
    request_map_dir: Path
    request_index_path: Path
    request_index_lock: threading.Lock = field(default_factory=threading.Lock)


def create_chat_state_store() -> ChatStateStore:
    return ChatStateStore(
        chat_job_lock=threading.Lock(),
        chat_job_event=threading.Event(),
        worker_started=False,
        lane_cursor=0,
    )


def create_chat_idempotency_store(chat_job_dir: Path) -> ChatIdempotencyStore:
    return ChatIdempotencyStore(
        request_map_dir=chat_job_dir / "request_index",
        request_index_path=chat_job_dir / "request_index.json",
    )
