from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from services.api.auth_service import AuthPrincipal
from services.api.teacher_grade_service import (
    TeacherGradeError,
    load_teacher_grade,
    official_score_from,
    save_teacher_grade,
)
from tests.helpers.app_factory import create_test_app


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _owner() -> AuthPrincipal:
    return AuthPrincipal(actor_id="t_zhang", role="teacher")


def _meta(**overrides: Any) -> dict:
    payload = {
        "assignment_id": "HW_1",
        "teacher_id": "t_zhang",
        "subject_id": "physics",
        "visibility_status": "published",
        "expected_students": ["S1"],
    }
    payload.update(overrides)
    return payload


class TestTeacherGradeService:
    def test_owner_can_override_score_comment_and_adopt_excerpts(self, tmp_path: Path) -> None:
        _write_json(tmp_path / "assignments" / "HW_1" / "meta.json", _meta())
        result = save_teacher_grade(
            "HW_1",
            "S1",
            principal=_owner(),
            data_dir=tmp_path,
            updates={
                "override_score": 12.5,
                "comment": "步骤完整，单位漏写",
                "adopted_coach_excerpts": [
                    {
                        "session_id": "ses_1",
                        "turn_ref": "ts:2026-08-28T12:01:00",
                        "text": "加速度是速度的变化率",
                    }
                ],
                "attempt_id": "submission_20260828T120000",
            },
        )
        assert result["ok"] is True
        stored = load_teacher_grade(tmp_path, "HW_1", "S1")
        assert stored is not None
        assert stored["schema"] == "teacher_grade/v1"
        assert stored["override_score_earned"] == 12.5
        assert stored["comment"] == "步骤完整，单位漏写"
        assert stored["attempt_id"] == "submission_20260828T120000"
        assert stored["teacher_id"] == "t_zhang"
        assert stored["adopted_coach_excerpts"][0]["text"] == "加速度是速度的变化率"
        grade_path = tmp_path / "student_submissions" / "HW_1" / "S1" / "teacher_grade.json"
        assert grade_path.exists()

    def test_partial_update_keeps_previous_override_score(self, tmp_path: Path) -> None:
        _write_json(tmp_path / "assignments" / "HW_1" / "meta.json", _meta())
        save_teacher_grade(
            "HW_1",
            "S1",
            principal=_owner(),
            data_dir=tmp_path,
            updates={"override_score": 9.0, "comment": "初评"},
        )
        save_teacher_grade(
            "HW_1",
            "S1",
            principal=_owner(),
            data_dir=tmp_path,
            updates={"comment": "终评"},
        )
        stored = load_teacher_grade(tmp_path, "HW_1", "S1")
        assert stored is not None
        assert stored["override_score_earned"] == 9.0
        assert stored["comment"] == "终评"

    def test_non_owner_cannot_grade(self, tmp_path: Path) -> None:
        _write_json(tmp_path / "assignments" / "HW_1" / "meta.json", _meta())
        try:
            save_teacher_grade(
                "HW_1",
                "S1",
                principal=AuthPrincipal(actor_id="t_li", role="teacher"),
                data_dir=tmp_path,
                updates={"comment": "nope"},
            )
        except TeacherGradeError as exc:
            assert exc.status_code == 403
            assert exc.detail == "forbidden_assignment_owner"
        else:
            raise AssertionError("expected TeacherGradeError")

    def test_official_score_uses_override_only_when_present(self) -> None:
        assert official_score_from(auto_score=8, teacher_grade=None) == 8.0
        assert (
            official_score_from(
                auto_score=8,
                teacher_grade={"override_score_earned": 11},
            )
            == 11.0
        )
        assert official_score_from(auto_score=8, teacher_grade={"comment": "no score"}) == 8.0
        assert official_score_from(auto_score=None, teacher_grade=None) is None


def test_grade_endpoint_writes_teacher_grade_json() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(
            tmp / "data" / "assignments" / "HW_1" / "meta.json",
            _meta(),
        )
        app_mod = create_test_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.post(
                "/teacher/assignment/HW_1/student/S1/grade",
                json={
                    "override_score": 10,
                    "comment": "采纳后的评语",
                    "adopted_coach_excerpts": [{"text": "先写单位"}],
                },
            )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        stored = json.loads(
            (tmp / "data" / "student_submissions" / "HW_1" / "S1" / "teacher_grade.json").read_text(
                encoding="utf-8"
            )
        )
        assert stored["override_score_earned"] == 10
        assert stored["comment"] == "采纳后的评语"
        assert stored["adopted_coach_excerpts"][0]["text"] == "先写单位"


def test_chat_comments_are_not_copied_until_adopted() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(tmp / "data" / "assignments" / "HW_1" / "meta.json", _meta())
        app_mod = create_test_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.post(
                "/teacher/assignment/HW_1/student/S1/grade",
                json={"comment": "老师自己写的评语"},
            )
        assert res.status_code == 200
        stored = json.loads(
            (tmp / "data" / "student_submissions" / "HW_1" / "S1" / "teacher_grade.json").read_text(
                encoding="utf-8"
            )
        )
        assert stored["comment"] == "老师自己写的评语"
        assert stored.get("adopted_coach_excerpts") == []
        assert stored.get("override_score_earned") is None
