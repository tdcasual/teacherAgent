import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_requirements_service import (
    AssignmentRequirementsDeps,
    compute_requirements_missing,
    ensure_requirements_for_assignment,
    format_requirements_prompt,
    merge_requirements,
    normalize_class_level,
    normalize_difficulty,
    normalize_preferences,
    parse_duration,
    parse_list_value,
    save_assignment_requirements,
    validate_requirements,
)


class AssignmentRequirementsServiceTest(unittest.TestCase):
    def _deps(self, root: Path) -> AssignmentRequirementsDeps:
        return AssignmentRequirementsDeps(
            data_dir=root / "data",
            now_iso=lambda: "2026-02-08T12:00:00",
        )

    def test_parse_and_normalize_helpers(self):
        self.assertEqual(parse_list_value("A, B;C"), ["A", "B", "C"])
        self.assertEqual(parse_list_value(["A", " ", "B"]), ["A", "B"])
        self.assertEqual(parse_list_value(None), [])

        prefs, invalid = normalize_preferences(["A", "提升", "X", "A基础"])
        self.assertEqual(prefs, ["A基础", "B提升"])
        self.assertEqual(invalid, ["X"])

        self.assertEqual(normalize_class_level("弱"), "偏弱")
        self.assertEqual(normalize_class_level("一般"), "中等")
        self.assertIsNone(normalize_class_level("未知"))

        self.assertEqual(parse_duration("40分钟"), 40)
        self.assertIsNone(parse_duration("abc"))

        self.assertEqual(normalize_difficulty("hard"), "advanced")
        self.assertEqual(normalize_difficulty("压轴题"), "challenge")
        self.assertEqual(normalize_difficulty(None), "basic")

    def test_validate_and_missing(self):
        payload = {
            "subject": "物理",
            "topic": "电流",
            "grade_level": "初二",
            "class_level": "中等",
            "core_concepts": ["电流", "电压", "电阻"],
            "typical_problem": "串并联计算",
            "misconceptions": ["概念混淆1", "概念混淆2", "概念混淆3", "概念混淆4"],
            "duration_minutes": 40,
            "preferences": ["A", "D探究"],
            "extra_constraints": "可用计算器",
        }
        normalized, errors = validate_requirements(payload)
        self.assertEqual(errors, [])
        self.assertEqual((normalized or {}).get("class_level"), "中等")
        self.assertEqual((normalized or {}).get("preferences"), ["A基础", "D探究"])
        self.assertEqual(compute_requirements_missing(payload), [])

        bad = {"subject": "", "preferences": ["X"], "duration_minutes": 25}
        missing = compute_requirements_missing(bad)
        self.assertIn("subject", missing)
        self.assertIn("preferences", missing)
        normalized_bad, errors_bad = validate_requirements(bad)
        self.assertIsNone(normalized_bad)
        self.assertTrue(errors_bad)

    def test_merge_requirements(self):
        base = {"core_concepts": ["电流"], "topic": "", "preferences": ["A基础"]}
        update = {"core_concepts": ["电压", "电阻"], "topic": "电学", "preferences": ["B"]}
        merged = merge_requirements(base, update, overwrite=False)
        self.assertEqual(merged.get("topic"), "电学")
        self.assertEqual(merged.get("core_concepts"), ["电流", "电压", "电阻"])
        self.assertEqual(merged.get("preferences"), ["A基础", "B"])

        merged_overwrite = merge_requirements(base, {"preferences": ["C生活应用"]}, overwrite=True)
        self.assertEqual(merged_overwrite.get("preferences"), ["C生活应用"])

    def test_save_and_ensure_requirements(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            valid_payload = {
                "subject": "物理",
                "topic": "欧姆定律",
                "grade_level": "初二",
                "class_level": "中等",
                "core_concepts": ["欧姆定律", "串联", "并联"],
                "typical_problem": "电路计算",
                "misconceptions": ["错1", "错2", "错3", "错4"],
                "duration_minutes": 40,
                "preferences": ["A", "B"],
                "extra_constraints": "",
            }
            save = save_assignment_requirements("A1_2026-02-08", valid_payload, "2026-02-08", deps=deps)
            self.assertTrue(save.get("ok"))
            req_path = Path(str(save.get("path") or ""))
            self.assertTrue(req_path.exists())
            data = json.loads(req_path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("created_at"), "2026-02-08T12:00:00")

            ensured = ensure_requirements_for_assignment(
                "A2_2026-02-08",
                "2026-02-08",
                valid_payload,
                source="manual",
                deps=deps,
            )
            self.assertTrue((ensured or {}).get("ok"))

            auto_skip = ensure_requirements_for_assignment(
                "A3_2026-02-08",
                "2026-02-08",
                None,
                source="auto",
                deps=deps,
            )
            self.assertIsNone(auto_skip)

            missing = ensure_requirements_for_assignment(
                "A4_2026-02-08",
                "2026-02-08",
                None,
                source="manual",
                deps=deps,
            )
            self.assertEqual((missing or {}).get("error"), "requirements_missing")

    def test_prompt_contains_template(self):
        prompt = format_requirements_prompt(errors=["1) 学科 必填"], include_assignment_id=True)
        self.assertIn("作业ID", prompt)
        self.assertIn("请按以下格式补全作业要求（8项）", prompt)


if __name__ == "__main__":
    unittest.main()
