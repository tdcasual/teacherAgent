"""Tests for services.api.skills.auto_route_rules — pure scoring functions."""

from __future__ import annotations

import pytest

from services.api.skills.auto_route_rules import score_role_skill

_KW = dict(assignment_intent=False, assignment_generation=False)


# ── Teacher: each skill_id returns positive score for matching text ──

@pytest.mark.parametrize("text,expected_hit", [
    ("请帮我生成作业", "生成作业"),
    ("布置作业给学生", "布置作业"),
    ("作业id是什么", "作业id"),
])
def test_homework_generator_matches(text, expected_hit):
    score, hits = score_role_skill("teacher", "physics-homework-generator", text, **_KW)
    assert score > 0
    assert expected_hit in hits


def test_homework_generator_intent_flags():
    score_both, h1 = score_role_skill(
        "teacher", "physics-homework-generator", "作业",
        assignment_intent=True, assignment_generation=True,
    )
    score_intent, h2 = score_role_skill(
        "teacher", "physics-homework-generator", "作业",
        assignment_intent=True, assignment_generation=False,
    )
    score_none, _ = score_role_skill(
        "teacher", "physics-homework-generator", "作业", **_KW,
    )
    assert score_both > score_intent > score_none
    assert "assignment_generation" in h1
    assert "assignment_intent" in h2


def test_llm_routing_matches():
    score, hits = score_role_skill("teacher", "physics-llm-routing", "模型路由配置 channel provider", **_KW)
    assert score > 0
    assert "routing_regex" in hits
    assert "channel" in hits
    assert "provider" in hits


def test_lesson_capture_matches():
    score, hits = score_role_skill("teacher", "physics-lesson-capture", "课堂采集材料", **_KW)
    assert score > 0
    assert "lesson_capture_combo" in hits


def test_core_examples_matches():
    score, hits = score_role_skill("teacher", "physics-core-examples", "请查看 CE123 核心例题", **_KW)
    assert score > 0
    assert "ce_id" in hits
    assert "核心例题" in hits


def test_student_focus_matches():
    score, hits = score_role_skill("teacher", "physics-student-focus", "该学生画像诊断", **_KW)
    assert score > 0
    assert "student_focus_combo" in hits
    assert "single_student_regex" in hits


def test_student_coach_teacher():
    score, hits = score_role_skill("teacher", "physics-student-coach", "开始今天作业", **_KW)
    assert score > 0
    assert "开始今天作业" in hits


def test_teacher_ops_matches():
    score, hits = score_role_skill("teacher", "physics-teacher-ops", "考试分析试卷备课", **_KW)
    assert score > 0
    assert "考试分析" in hits
    assert "试卷" in hits
    assert "备课" in hits


# ── Non-matching text returns 0 ──

def test_non_matching_text_returns_zero():
    score, hits = score_role_skill("teacher", "physics-homework-generator", "今天天气不错", **_KW)
    assert score == 0
    assert hits == []


# ── Unknown skill_id returns 0 ──

def test_unknown_skill_returns_zero():
    score, hits = score_role_skill("teacher", "nonexistent-skill", "生成作业", **_KW)
    assert score == 0
    assert hits == []


# ── Student role only scores physics-student-coach ──

def test_student_role_coach_positive():
    score, hits = score_role_skill("student", "physics-student-coach", "开始今天作业讲解错题", **_KW)
    assert score > 0
    assert "开始今天作业" in hits


def test_student_role_other_skill_zero():
    score, hits = score_role_skill("student", "physics-homework-generator", "生成作业", **_KW)
    assert score == 0
    assert hits == []


# ── Unknown role returns 0 ──

@pytest.mark.parametrize("role", [None, "", "admin", "unknown"])
def test_unknown_role_returns_zero(role):
    score, hits = score_role_skill(role, "physics-homework-generator", "生成作业", **_KW)
    assert score == 0
    assert hits == []
