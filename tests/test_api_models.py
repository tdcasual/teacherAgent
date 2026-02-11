"""Tests for services.api.api_models Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.api.api_models import (
    AssignmentRequirementsRequest,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStartRequest,
    TeacherSkillCreateRequest,
    TeacherSkillImportRequest,
)


# ── ChatMessage ──────────────────────────────────────────────────────

class TestChatMessage:
    def test_valid(self):
        m = ChatMessage(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"

    def test_missing_role(self):
        with pytest.raises(ValidationError):
            ChatMessage(content="hello")

    def test_missing_content(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="user")


# ── ChatRequest ──────────────────────────────────────────────────────

class TestChatRequest:
    def test_messages_only(self):
        req = ChatRequest(messages=[ChatMessage(role="user", content="hi")])
        assert len(req.messages) == 1
        assert req.role is None
        assert req.agent_id is None
        assert req.skill_id is None
        assert req.auto_generate_assignment is None

    def test_all_optional_fields(self):
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="hi")],
            role="teacher",
            agent_id="a1",
            skill_id="s1",
            teacher_id="t1",
            student_id="st1",
            assignment_id="as1",
            assignment_date="2026-01-01",
            auto_generate_assignment=True,
        )
        assert req.role == "teacher"
        assert req.agent_id == "a1"
        assert req.auto_generate_assignment is True

    def test_missing_messages(self):
        with pytest.raises(ValidationError):
            ChatRequest()


# ── ChatStartRequest ─────────────────────────────────────────────────

class TestChatStartRequest:
    def test_requires_request_id(self):
        with pytest.raises(ValidationError):
            ChatStartRequest(messages=[ChatMessage(role="user", content="hi")])

    def test_valid_with_request_id(self):
        req = ChatStartRequest(
            messages=[ChatMessage(role="user", content="hi")],
            request_id="r-1",
        )
        assert req.request_id == "r-1"
        assert req.session_id is None

    def test_inherits_chat_request_fields(self):
        req = ChatStartRequest(
            messages=[ChatMessage(role="user", content="hi")],
            request_id="r-2",
            skill_id="sk",
        )
        assert req.skill_id == "sk"


# ── AssignmentRequirementsRequest ────────────────────────────────────

class TestAssignmentRequirementsRequest:
    def test_valid(self):
        req = AssignmentRequirementsRequest(
            assignment_id="a1", requirements={"topic": "gravity"}
        )
        assert req.assignment_id == "a1"
        assert req.date is None
        assert req.created_by is None

    def test_missing_assignment_id(self):
        with pytest.raises(ValidationError):
            AssignmentRequirementsRequest(requirements={"x": 1})

    def test_missing_requirements(self):
        with pytest.raises(ValidationError):
            AssignmentRequirementsRequest(assignment_id="a1")


# ── TeacherSkillCreateRequest ────────────────────────────────────────

class TestTeacherSkillCreateRequest:
    def test_defaults(self):
        req = TeacherSkillCreateRequest(title="My Skill", description="desc")
        assert req.keywords == []
        assert req.examples == []
        assert req.allowed_roles == ["teacher"]

    def test_title_too_long(self):
        with pytest.raises(ValidationError):
            TeacherSkillCreateRequest(title="x" * 201, description="ok")

    def test_missing_title(self):
        with pytest.raises(ValidationError):
            TeacherSkillCreateRequest(description="desc")


# ── ChatResponse ─────────────────────────────────────────────────────

class TestChatResponse:
    def test_valid(self):
        resp = ChatResponse(reply="ok")
        assert resp.reply == "ok"
        assert resp.role is None

    def test_with_role(self):
        resp = ChatResponse(reply="ok", role="assistant")
        assert resp.role == "assistant"


# ── TeacherSkillImportRequest ────────────────────────────────────────

class TestTeacherSkillImportRequest:
    def test_valid(self):
        req = TeacherSkillImportRequest(github_url="https://github.com/a/b")
        assert req.github_url == "https://github.com/a/b"

    def test_missing_url(self):
        with pytest.raises(ValidationError):
            TeacherSkillImportRequest()
