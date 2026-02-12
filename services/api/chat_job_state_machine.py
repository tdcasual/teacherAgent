from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

_TRANSITIONS: Dict[str, Set[str]] = {
    "queued": {"queued", "processing", "failed", "cancelled"},
    "processing": {"processing", "done", "failed", "cancelled"},
    "done": {"done"},
    "failed": {"failed"},
    "cancelled": {"cancelled"},
}

_ACTIVE_STATUSES = {"queued", "processing"}
_TERMINAL_STATUSES = {"done", "failed", "cancelled"}


def normalize_chat_job_status(status: object) -> str:
    text = str(status or "").strip().lower()
    return text or "queued"


def can_requeue_chat_job(status: object) -> bool:
    return normalize_chat_job_status(status) in _ACTIVE_STATUSES


def is_terminal_chat_job_status(status: object) -> bool:
    return normalize_chat_job_status(status) in _TERMINAL_STATUSES


@dataclass
class ChatJobStateMachine:
    status: str

    def __post_init__(self) -> None:
        self.status = normalize_chat_job_status(self.status)

    def transition(self, next_status: object) -> str:
        target = normalize_chat_job_status(next_status)
        allowed = _TRANSITIONS.get(self.status)
        if not allowed or target not in allowed:
            raise ValueError(f"invalid_chat_job_transition:{self.status}->{target}")
        self.status = target
        return self.status


def transition_chat_job_status(current_status: object, target_status: object) -> str:
    sm = ChatJobStateMachine(normalize_chat_job_status(current_status))
    return sm.transition(target_status)
