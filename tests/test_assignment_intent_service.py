import unittest

from services.api.assignment_intent_service import (
    detect_assignment_intent,
    extract_assignment_id,
    extract_date,
    extract_kp_list,
    extract_per_kp,
    extract_question_ids,
    extract_requirements_from_text,
    parse_grade_and_level,
    parse_subject_topic,
)


class AssignmentIntentServiceTest(unittest.TestCase):
    def test_detect_and_extract_assignment_basics(self):
        text = "请帮我生成作业，作业ID A2403_2026-02-04，日期 2026-02-04，知识点: 电流,电压。每个3题，Q1 Q2。"
        self.assertTrue(detect_assignment_intent(text))
        self.assertEqual(extract_assignment_id(text), "A2403_2026-02-04")
        self.assertEqual(extract_date(text), "2026-02-04")
        self.assertEqual(extract_kp_list(text), ["电流", "电压"])
        self.assertEqual(extract_per_kp(text), 3)
        self.assertEqual(extract_question_ids(text), ["Q1", "Q2"])

    def test_parse_subject_and_grade_level(self):
        subject, topic = parse_subject_topic("物理：串并联电路")
        self.assertEqual(subject, "物理")
        self.assertEqual(topic, "串并联电路")

        grade, level = parse_grade_and_level("初二 中等")
        self.assertEqual(grade, "初二")
        self.assertEqual(level, "中等")

    def test_extract_requirements_from_numbered_block(self):
        text = (
            "1）物理：电流与电压\n"
            "2）初二 & 中等\n"
            "3）电流,电压,电阻\n"
            "4）串并联综合题\n"
            "5）单位混淆,串并联识别错,公式套用错,审题不全\n"
            "6）40分钟\n"
            "7）A基础,B提升\n"
            "8）允许计算器"
        )
        req = extract_requirements_from_text(text)
        self.assertEqual(req.get("subject"), "物理")
        self.assertEqual(req.get("topic"), "电流与电压")
        self.assertEqual(req.get("class_level"), "中等")
        self.assertEqual(req.get("duration_minutes"), 40)
        self.assertEqual(req.get("preferences"), ["A基础", "B提升"])


if __name__ == "__main__":
    unittest.main()
