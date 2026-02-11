"""Tests for pure functions in services.api.chat_support_service."""
from __future__ import annotations

import pytest

from services.api.chat_support_service import (
    allowed_tools,
    build_interaction_note,
    build_verified_student_context,
    detect_latex_tokens,
    detect_math_delimiters,
    detect_student_study_trigger,
    extract_diagnostic_signals,
    extract_exam_id,
    extract_min_chars_requirement,
    is_exam_analysis_request,
    normalize_math_delimiters,
)


# ── build_verified_student_context ──────────────────────────────────────

class TestBuildVerifiedStudentContext:
    def test_full_profile(self):
        ctx = build_verified_student_context("S001", {"student_name": "张三", "class_name": "高一(1)班"})
        assert "student_id: S001" in ctx
        assert "姓名: 张三" in ctx
        assert "班级: 高一(1)班" in ctx
        assert "---BEGIN DATA---" in ctx

    def test_empty_profile(self):
        ctx = build_verified_student_context("S002")
        assert "student_id: S002" in ctx
        assert "(empty)" not in ctx  # student_id present so not empty

    def test_no_id_no_profile(self):
        ctx = build_verified_student_context("")
        assert "(empty)" in ctx


# ── detect_student_study_trigger ────────────────────────────────────────

class TestDetectStudentStudyTrigger:
    @pytest.mark.parametrize("text", ["开始今天作业", "我要开始作业", "进入作业模式", "开始练习", "开始诊断", "进入诊断"])
    def test_matching(self, text):
        assert detect_student_study_trigger(text) is True

    def test_non_matching(self):
        assert detect_student_study_trigger("你好老师") is False

    def test_empty(self):
        assert detect_student_study_trigger("") is False


# ── extract_diagnostic_signals ──────────────────────────────────────────

class TestExtractDiagnosticSignals:
    def test_weak_kp(self):
        sig = extract_diagnostic_signals("你在力学方面比较薄弱，需要加强运动学的练习")
        assert "力学" in sig.weak_kp

    def test_strong_kp(self):
        sig = extract_diagnostic_signals("电场部分掌握得不错，继续保持")
        assert "电场" in sig.strong_kp

    def test_topic_bracket(self):
        sig = extract_diagnostic_signals("【牛顿第二定律】这道题考查的是...")
        assert "牛顿第二定律" == sig.topic

    def test_empty_text(self):
        sig = extract_diagnostic_signals("")
        assert sig.weak_kp == []
        assert sig.strong_kp == []
        assert sig.topic == ""


# ── build_interaction_note ──────────────────────────────────────────────

class TestBuildInteractionNote:
    def test_with_assignment(self):
        note = build_interaction_note("我不懂", "这道题考查电场", assignment_id="HW01")
        assert "作业=HW01" in note

    def test_without_signals(self):
        note = build_interaction_note("你好", "你好同学")
        assert "[回复]" in note


# ── detect_math_delimiters ──────────────────────────────────────────────

class TestDetectMathDelimiters:
    def test_double_dollar(self):
        assert detect_math_delimiters("公式 $$E=mc^2$$") is True

    def test_single_dollar(self):
        assert detect_math_delimiters("速度 $v$") is True

    def test_backslash_bracket(self):
        assert detect_math_delimiters("公式 \\[F=ma\\]") is True

    def test_no_math(self):
        assert detect_math_delimiters("普通文本") is False

    def test_empty(self):
        assert detect_math_delimiters("") is False


# ── detect_latex_tokens ─────────────────────────────────────────────────

class TestDetectLatexTokens:
    def test_frac(self):
        assert detect_latex_tokens("\\frac{1}{2}") is True

    def test_no_tokens(self):
        assert detect_latex_tokens("普通文本") is False

    def test_empty(self):
        assert detect_latex_tokens("") is False


# ── normalize_math_delimiters ───────────────────────────────────────────

class TestNormalizeMathDelimiters:
    def test_replaces_brackets(self):
        assert normalize_math_delimiters("\\[F=ma\\]") == "$$F=ma$$"

    def test_replaces_parens(self):
        assert normalize_math_delimiters("\\(v\\)") == "$v$"

    def test_empty(self):
        assert normalize_math_delimiters("") == ""


# ── allowed_tools ───────────────────────────────────────────────────────

class TestAllowedTools:
    def test_teacher(self):
        tools = allowed_tools("teacher")
        assert len(tools) > 0
        assert "exam.list" in tools

    def test_student(self):
        assert allowed_tools("student") == set()

    def test_none(self):
        assert allowed_tools(None) == set()


# ── extract_min_chars_requirement ───────────────────────────────────────

class TestExtractMinCharsRequirement:
    def test_bu_shao_yu(self):
        assert extract_min_chars_requirement("不少于500字") == 500

    def test_yi_shang(self):
        assert extract_min_chars_requirement("800字以上") == 800

    def test_no_match(self):
        assert extract_min_chars_requirement("随便写") is None

    def test_empty(self):
        assert extract_min_chars_requirement("") is None


# ── extract_exam_id ─────────────────────────────────────────────────────

class TestExtractExamId:
    def test_found(self):
        assert extract_exam_id("请分析EX001的成绩") == "EX001"

    def test_no_match(self):
        assert extract_exam_id("没有考试编号") is None

    def test_empty(self):
        assert extract_exam_id("") is None


# ── is_exam_analysis_request ────────────────────────────────────────────

class TestIsExamAnalysisRequest:
    def test_direct_keyword(self):
        assert is_exam_analysis_request("请做考试分析") is True

    def test_split_keywords(self):
        assert is_exam_analysis_request("帮我分析一下这次考试") is True

    def test_unrelated(self):
        assert is_exam_analysis_request("今天天气不错") is False

    def test_empty(self):
        assert is_exam_analysis_request("") is False
