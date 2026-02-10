"""Tests for diagnostic signal extraction from LLM replies."""
import unittest

from services.api.chat_support_service import (
    DiagnosticSignals,
    build_interaction_note,
    extract_diagnostic_signals,
)


class TestExtractDiagnosticSignals(unittest.TestCase):
    def test_empty_text_returns_empty_signals(self):
        signals = extract_diagnostic_signals("")
        self.assertEqual(signals.weak_kp, [])
        self.assertEqual(signals.strong_kp, [])
        self.assertEqual(signals.next_focus, "")

    def test_extracts_weak_kp(self):
        reply = "你在牛顿第二定律方面掌握不够，受力分析也需要加强。"
        signals = extract_diagnostic_signals(reply)
        self.assertIn("牛顿", signals.weak_kp)
        self.assertIn("受力分析", signals.weak_kp)

    def test_extracts_strong_kp(self):
        reply = "你对运动学的理解正确，加速度的概念掌握得不错。"
        signals = extract_diagnostic_signals(reply)
        self.assertIn("运动学", signals.strong_kp)
        self.assertIn("加速度", signals.strong_kp)

    def test_extracts_misconceptions(self):
        reply = "注意区分速度和加速度的概念，这是常见错误。"
        signals = extract_diagnostic_signals(reply)
        self.assertTrue(len(signals.misconceptions) > 0)
        self.assertTrue(any("注意区分" in m for m in signals.misconceptions))

    def test_extracts_next_focus(self):
        reply = "建议重点复习电路和欧姆定律的相关内容。"
        signals = extract_diagnostic_signals(reply)
        self.assertIn("建议", signals.next_focus)

    def test_extracts_topic_from_brackets(self):
        reply = "【诊断问题】Q1\n题目：一个质量为m的物体..."
        signals = extract_diagnostic_signals(reply)
        self.assertEqual(signals.topic, "诊断问题")

    def test_no_false_positives_on_plain_text(self):
        reply = "好的，我们来看下一道题。"
        signals = extract_diagnostic_signals(reply)
        self.assertEqual(signals.weak_kp, [])
        self.assertEqual(signals.strong_kp, [])
        self.assertEqual(signals.misconceptions, [])
        self.assertEqual(signals.next_focus, "")


class TestBuildInteractionNote(unittest.TestCase):
    def test_structured_note_with_signals(self):
        reply = "你在牛顿第二定律方面掌握不够，建议复习受力分析。"
        note = build_interaction_note("请讲一下力学", reply)
        self.assertIn("[诊断]", note)
        self.assertIn("[学生]", note)
        self.assertLessEqual(len(note), 201)  # 200 + possible "…"

    def test_fallback_note_without_signals(self):
        note = build_interaction_note("你好", "你好，有什么可以帮你的？")
        self.assertIn("[回复]", note)

    def test_note_truncation(self):
        long_reply = "建议复习" + "牛顿" * 100
        note = build_interaction_note("x" * 100, long_reply)
        self.assertLessEqual(len(note), 201)

    def test_assignment_id_included(self):
        note = build_interaction_note("开始", "好的", assignment_id="HW-001")
        self.assertIn("HW-001", note)


if __name__ == "__main__":
    unittest.main()
