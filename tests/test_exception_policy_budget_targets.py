from __future__ import annotations

from pathlib import Path


def _entries() -> list[str]:
    path = Path("config/exception_policy_allowlist.txt")
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_chat_lock_allowlist_entries_reduced_to_budget() -> None:
    rows = _entries()
    chat_lock_rows = [row for row in rows if row.startswith("services/api/chat_lock_service.py:")]
    assert len(chat_lock_rows) <= 10, f"chat_lock allowlist too high: {len(chat_lock_rows)}"


def test_global_allowlist_entries_reduced_to_budget() -> None:
    rows = _entries()
    assert len(rows) <= 340, f"allowlist still too high: {len(rows)}"
