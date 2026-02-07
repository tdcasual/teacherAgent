from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.chat_session_history_service import load_session_messages


class ChatSessionHistoryServiceTest(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        result = load_session_messages(Path("/tmp/definitely-missing-session.jsonl"), cursor=-1, limit=50, direction="backward")
        self.assertEqual(result.get("messages"), [])

    def test_backward_mode_returns_tail_messages(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "s.jsonl"
            rows = [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
            ]
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
            result = load_session_messages(path, cursor=-1, limit=2, direction="backward")
            messages = result.get("messages") or []
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0].get("content"), "a1")
            self.assertEqual(messages[1].get("content"), "u2")

    def test_forward_mode_uses_cursor(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "s.jsonl"
            rows = [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
            ]
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
            result = load_session_messages(path, cursor=1, limit=2, direction="forward")
            messages = result.get("messages") or []
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0].get("content"), "a1")
            self.assertEqual(messages[1].get("content"), "u2")


if __name__ == "__main__":
    unittest.main()
