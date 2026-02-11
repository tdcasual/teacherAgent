"""Tests for services.api.subject_score_guard_service — pure-function guard logic."""

from __future__ import annotations

import pytest

from services.api.subject_score_guard_service import (
    _contains_token,
    _detect_subject_keys,
    extract_requested_subject,
    infer_exam_subject_from_overview,
    looks_like_subject_score_request,
    should_guard_total_mode_subject_request,
    subject_display,
)


# ── subject_display ──────────────────────────────────────────────────

class TestSubjectDisplay:
    def test_known_keys(self):
        assert subject_display("physics") == "物理"
        assert subject_display("math") == "数学"
        assert subject_display("english") == "英语"

    def test_case_insensitive(self):
        assert subject_display("Physics") == "物理"
        assert subject_display("CHEMISTRY") == "化学"

    def test_fallback(self):
        assert subject_display("unknown") == "单科"
        assert subject_display(None) == "单科"
        assert subject_display("") == "单科"


# ── _contains_token ──────────────────────────────────────────────────

class TestContainsToken:
    def test_cjk_substring(self):
        assert _contains_token("我的物理成绩", "我的物理成绩", "物理") is True

    def test_ascii_word_boundary(self):
        assert _contains_token("my physics score", "my physics score", "physics") is True
        assert _contains_token("astrophysics", "astrophysics", "physics") is False

    def test_empty_inputs(self):
        assert _contains_token("", "", "physics") is False
        assert _contains_token("hello", "hello", "") is False
        assert _contains_token("hello", "hello", None) is False

    def test_separator_normalisation(self):
        assert _contains_token("sub-math-test", "sub-math-test", "math") is True
        assert _contains_token("sub_math_test", "sub_math_test", "math") is True


# ── _detect_subject_keys ─────────────────────────────────────────────

class TestDetectSubjectKeys:
    def test_single_subject(self):
        assert _detect_subject_keys("物理考试") == {"physics"}

    def test_multiple_subjects(self):
        keys = _detect_subject_keys("物理和化学成绩")
        assert keys == {"physics", "chemistry"}

    def test_no_subject(self):
        assert _detect_subject_keys("今天天气不错") == set()

    def test_none_and_empty(self):
        assert _detect_subject_keys(None) == set()
        assert _detect_subject_keys("") == set()


# ── looks_like_subject_score_request ─────────────────────────────────

class TestLooksLikeSubjectScoreRequest:
    def test_score_and_subject(self):
        assert looks_like_subject_score_request("物理成绩") is True
        assert looks_like_subject_score_request("查看数学分数") is True

    def test_score_only(self):
        assert looks_like_subject_score_request("成绩如何") is False

    def test_subject_only(self):
        assert looks_like_subject_score_request("物理很难") is False

    def test_generic_subject_hint(self):
        assert looks_like_subject_score_request("单科成绩") is True

    def test_empty(self):
        assert looks_like_subject_score_request("") is False
        assert looks_like_subject_score_request(None) is False


# ── extract_requested_subject ────────────────────────────────────────

class TestExtractRequestedSubject:
    def test_single_subject(self):
        assert extract_requested_subject("物理成绩") == "physics"

    def test_two_subjects_returns_none(self):
        assert extract_requested_subject("物理和化学") is None

    def test_no_subject(self):
        assert extract_requested_subject("你好") is None
        assert extract_requested_subject("") is None
        assert extract_requested_subject(None) is None


# ── infer_exam_subject_from_overview ─────────────────────────────────

class TestInferExamSubjectFromOverview:
    def test_meta_subject(self):
        overview = {"meta": {"subject": "物理"}}
        assert infer_exam_subject_from_overview(overview) == "physics"

    def test_empty_overview(self):
        assert infer_exam_subject_from_overview({}) is None

    def test_multiple_subjects_returns_none(self):
        overview = {"meta": {"subject": "物理"}, "notes": "化学实验"}
        assert infer_exam_subject_from_overview(overview) is None

    def test_non_dict(self):
        assert infer_exam_subject_from_overview(None) is None


# ── should_guard_total_mode_subject_request ──────────────────────────

class TestShouldGuardTotalMode:
    def test_non_total_mode(self):
        overview = {"score_mode": "per_question", "meta": {"subject": "物理"}}
        guarded, req, inf = should_guard_total_mode_subject_request("物理成绩", overview)
        assert guarded is False

    def test_total_mode(self):
        overview = {"score_mode": "total", "meta": {"subject": "化学"}}
        guarded, req, inf = should_guard_total_mode_subject_request("化学成绩", overview)
        assert guarded is True
        assert req == "chemistry"
        assert inf == "chemistry"

    def test_total_mode_no_subject_in_text(self):
        overview = {"score_mode": "total", "meta": {"subject": "数学"}}
        guarded, req, inf = should_guard_total_mode_subject_request("你好", overview)
        assert guarded is True
        assert req is None
        assert inf == "math"

    def test_empty_overview(self):
        guarded, req, inf = should_guard_total_mode_subject_request("物理", {})
        assert guarded is False
