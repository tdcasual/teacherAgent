import unittest

from services.api.session_history_api_service import (
    SessionHistoryApiDeps,
    SessionHistoryApiError,
    student_history_sessions,
    update_student_session_view_state,
)


class SessionHistoryApiServiceTest(unittest.TestCase):
    def _deps(self):
        states = {"s1": {"updated_at": "2026-02-07T12:00:00.000"}}

        def _load_student_state(student_id):  # type: ignore[no-untyped-def]
            return dict(states.get(student_id) or {"updated_at": ""})

        def _save_student_state(student_id, state):  # type: ignore[no-untyped-def]
            states[student_id] = dict(state)

        return SessionHistoryApiDeps(
            load_student_sessions_index=lambda _sid: [{"session_id": "a"}],
            load_teacher_sessions_index=lambda _tid: [{"session_id": "t"}],
            paginate_session_items=lambda items, cursor, limit: (items[cursor : cursor + limit], None, len(items)),
            load_student_session_view_state=_load_student_state,
            load_teacher_session_view_state=lambda _tid: {"updated_at": ""},
            normalize_session_view_state_payload=lambda payload: dict(payload),
            compare_iso_ts=lambda a, b: (1 if (a or "") > (b or "") else -1 if (a or "") < (b or "") else 0),
            now_iso_millis=lambda: "2026-02-07T12:00:01.000",
            save_student_session_view_state=_save_student_state,
            save_teacher_session_view_state=lambda _tid, _state: None,
            student_session_file=lambda _sid, _sess: "dummy",
            teacher_session_file=lambda _tid, _sess: "dummy",
            load_session_messages=lambda *_args, **_kwargs: {"messages": [], "next_cursor": None},
            resolve_teacher_id=lambda tid: (tid or "teacher"),
        )

    def test_student_history_requires_student_id(self):
        with self.assertRaises(SessionHistoryApiError):
            student_history_sessions("", limit=20, cursor=0, deps=self._deps())

    def test_update_student_state_rejects_stale(self):
        deps = self._deps()
        result = update_student_session_view_state(
            {"student_id": "s1", "state": {"updated_at": "2026-02-07T11:59:59.000"}},
            deps=deps,
        )
        self.assertTrue(result.get("stale"))


if __name__ == "__main__":
    unittest.main()
