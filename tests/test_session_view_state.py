import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.session_view_state import compare_iso_ts, load_session_view_state, normalize_session_view_state_payload, save_session_view_state


class SessionViewStateTest(unittest.TestCase):
    def test_normalize_trims_and_dedupes_fields(self):
        payload = normalize_session_view_state_payload(
            {
                "title_map": {"  s1  ": "  章节一  ", "": "x"},
                "hidden_ids": [" a ", "", "a", "b"],
                "active_session_id": "  main  ",
                "updated_at": "invalid",
            }
        )
        self.assertEqual(payload["title_map"], {"s1": "章节一"})
        self.assertEqual(payload["hidden_ids"], ["a", "b"])
        self.assertEqual(payload["active_session_id"], "main")
        self.assertEqual(payload["updated_at"], "")

    def test_compare_iso_ts_orders_values(self):
        self.assertEqual(compare_iso_ts("2026-02-07T10:00:00", "2026-02-07T09:59:59"), 1)
        self.assertEqual(compare_iso_ts("2026-02-07T09:59:59", "2026-02-07T10:00:00"), -1)
        self.assertEqual(compare_iso_ts("2026-02-07T10:00:00", "2026-02-07T10:00:00"), 0)

    def test_save_and_load_roundtrip(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "view_state.json"
            save_session_view_state(
                path,
                {
                    "title_map": {"s1": "章节一"},
                    "hidden_ids": ["x1"],
                    "active_session_id": "main",
                    "updated_at": "2026-02-07T10:00:00.000",
                },
            )

            loaded = load_session_view_state(path)
            self.assertEqual(loaded["title_map"], {"s1": "章节一"})
            self.assertEqual(loaded["hidden_ids"], ["x1"])
            self.assertEqual(loaded["active_session_id"], "main")
            self.assertEqual(loaded["updated_at"], "2026-02-07T10:00:00.000")

            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["active_session_id"], "main")


if __name__ == "__main__":
    unittest.main()
