import unittest
from pathlib import Path

from services.api.assignment_today_service import AssignmentTodayDeps, assignment_today


class AssignmentTodayServiceTest(unittest.TestCase):
    def test_returns_none_when_assignment_missing_without_auto_generate(self):
        deps = AssignmentTodayDeps(
            data_dir=Path("/tmp/data"),
            parse_date_str=lambda value: str(value or "2026-02-08"),
            has_llm_key=lambda: True,
            load_profile_file=lambda _path: {},
            find_assignment_for_date=lambda *_args, **_kwargs: None,
            derive_kp_from_profile=lambda _profile: ["力学"],
            safe_assignment_id=lambda student_id, date_str: f"{student_id}_{date_str}",
            assignment_generate=lambda _args: {"ok": True},
            load_assignment_meta=lambda _folder: {},
            build_assignment_detail=lambda _folder, include_text=False: {"include_text": include_text},
        )

        result = assignment_today(
            student_id="S1",
            date="2026-02-08",
            auto_generate=False,
            generate=True,
            per_kp=5,
            deps=deps,
        )

        self.assertEqual(result, {"date": "2026-02-08", "assignment": None})

    def test_auto_generate_builds_default_kp_and_disables_generate_without_key(self):
        captured = {}

        def _assignment_generate(args):
            captured["args"] = dict(args)
            return {"ok": True}

        deps = AssignmentTodayDeps(
            data_dir=Path("/tmp/data"),
            parse_date_str=lambda value: str(value or "2026-02-08"),
            has_llm_key=lambda: False,
            load_profile_file=lambda _path: {"class_name": "高二2403班"},
            find_assignment_for_date=lambda *_args, **_kwargs: None,
            derive_kp_from_profile=lambda _profile: [],
            safe_assignment_id=lambda student_id, date_str: f"A_{student_id}_{date_str}",
            assignment_generate=_assignment_generate,
            load_assignment_meta=lambda _folder: {"assignment_id": "A_S1_2026-02-08"},
            build_assignment_detail=lambda folder, include_text=False: {
                "folder": str(folder),
                "include_text": include_text,
            },
        )

        result = assignment_today(
            student_id="S1",
            date="2026-02-08",
            auto_generate=True,
            generate=True,
            per_kp=3,
            deps=deps,
        )

        self.assertEqual(captured["args"]["kp"], "uncategorized")
        self.assertEqual(captured["args"]["generate"], False)
        self.assertEqual(captured["args"]["class_name"], "高二2403班")
        self.assertEqual(result["assignment"]["include_text"], True)


if __name__ == "__main__":
    unittest.main()
