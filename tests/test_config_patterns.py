"""Tests for teacher-memory pattern constants in services.api.config."""

from __future__ import annotations

import pytest

from services.api.config import (
    _TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
    _TEACHER_MEMORY_CONFLICT_GROUPS,
    _TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
    _TEACHER_MEMORY_SENSITIVE_PATTERNS,
    _TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
)


def _any_match(patterns, text: str) -> bool:
    return any(p.search(text) for p in patterns)


# -- durable intent ----------------------------------------------------------

class TestDurableIntentPatterns:
    @pytest.mark.parametrize("text", [
        "请记住这个格式", "帮我记住偏好", "以后都用这个",
        "默认按这个来", "长期按此格式", "固定格式输出",
        "偏好是简洁", "今后都统一",
    ])
    def test_matches_expected(self, text):
        assert _any_match(_TEACHER_MEMORY_DURABLE_INTENT_PATTERNS, text)

    @pytest.mark.parametrize("text", ["今天先这样", "帮我解这道题", "你好"])
    def test_rejects_unrelated(self, text):
        assert not _any_match(_TEACHER_MEMORY_DURABLE_INTENT_PATTERNS, text)


# -- temporary hint -----------------------------------------------------------

class TestTemporaryHintPatterns:
    @pytest.mark.parametrize("text", [
        "今天先按简洁来", "本周用英文", "这次用段落",
        "临时改一下", "暂时不要", "先按这个格式",
    ])
    def test_matches_expected(self, text):
        assert _any_match(_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS, text)

    @pytest.mark.parametrize("text", ["请记住格式", "默认用中文", "长期按此"])
    def test_rejects_unrelated(self, text):
        assert not _any_match(_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS, text)


# -- auto-infer stable -------------------------------------------------------

class TestAutoInferStablePatterns:
    @pytest.mark.parametrize("text", [
        "输出用markdown", "格式要简洁", "结论放前面",
        "难度适中", "反馈要详细", "分点列出",
    ])
    def test_matches_expected(self, text):
        assert _any_match(_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS, text)

    @pytest.mark.parametrize("text", ["你好世界", "天气不错"])
    def test_rejects_unrelated(self, text):
        assert not _any_match(_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS, text)


# -- auto-infer block ---------------------------------------------------------

class TestAutoInferBlockPatterns:
    @pytest.mark.parametrize("text", [
        "这道题怎么做", "这次先这样", "帮我解一下",
        "本题答案", "临时改改", "算一下结果",
    ])
    def test_matches_expected(self, text):
        assert _any_match(_TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS, text)

    @pytest.mark.parametrize("text", ["请记住偏好", "默认格式", "长期使用"])
    def test_rejects_unrelated(self, text):
        assert not _any_match(_TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS, text)


# -- sensitive patterns -------------------------------------------------------

class TestSensitivePatterns:
    @pytest.mark.parametrize("text", [
        "sk-abc123XYZ456abcd7890",
        "AIzaSyB0EXAMPLE0KEY012345678",
        "AKIA1234567890AB",
        "api_key=someSecretValue",
        "access-token: ghp_xxxxxxxxxxxx",
        "password=hunter2abc",
        "secret_key = sk_live_abcdef",
    ])
    def test_matches_api_keys(self, text):
        assert _any_match(_TEACHER_MEMORY_SENSITIVE_PATTERNS, text)

    @pytest.mark.parametrize("text", [
        "普通聊天内容", "请记住格式偏好", "sk-short",
    ])
    def test_rejects_normal_text(self, text):
        assert not _any_match(_TEACHER_MEMORY_SENSITIVE_PATTERNS, text)


# -- conflict groups ----------------------------------------------------------

class TestConflictGroups:
    def test_is_list_of_tuple_pairs(self):
        assert isinstance(_TEACHER_MEMORY_CONFLICT_GROUPS, list)
        assert len(_TEACHER_MEMORY_CONFLICT_GROUPS) >= 2
        for group in _TEACHER_MEMORY_CONFLICT_GROUPS:
            assert isinstance(group, tuple) and len(group) == 2
            group_a, group_b = group
            assert isinstance(group_a, tuple) and len(group_a) >= 2
            assert isinstance(group_b, tuple) and len(group_b) >= 2
            assert all(isinstance(s, str) for s in group_a)
            assert all(isinstance(s, str) for s in group_b)

    def test_no_overlap_within_pair(self):
        for group_a, group_b in _TEACHER_MEMORY_CONFLICT_GROUPS:
            assert not set(group_a) & set(group_b), "conflict sides must not overlap"
