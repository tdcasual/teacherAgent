from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from llm_gateway import Target, UnifiedLLMResponse
from services.api.assignment_rubric_service import (
    load_assignment_rubric,
    parse_rubric_markdown,
    run_rubric_suggest_job,
)


def test_parse_markdown_checklist() -> None:
    items = parse_rubric_markdown(
        "# 量规\n- 能指出情景约束\n* 能解释因果\n1. 有观察记录\n2) 不编未做实验\n"
    )
    assert [item["id"] for item in items] == ["1", "2", "3", "4"]
    assert items[0]["text"] == "能指出情景约束"
    assert items[1]["text"] == "能解释因果"
    assert items[2]["text"] == "有观察记录"
    assert items[3]["text"] == "不编未做实验"
    assert all(item.get("max_points") is None for item in items)

    whole = parse_rubric_markdown("整体按完成度目测。")
    assert len(whole) == 1
    assert whole[0]["id"] == "whole"
    assert "整体按完成度目测" in whole[0]["text"]


def test_missing_rubric_is_source_none(tmp_path: Path) -> None:
    folder = tmp_path / "assignments" / "hw1"
    folder.mkdir(parents=True, exist_ok=True)
    loaded = load_assignment_rubric(folder)
    assert loaded["source"] == "none"
    assert loaded["items"] == []

    (folder / "rubric.md").write_text("- 能指出情景约束\n", encoding="utf-8")
    present = load_assignment_rubric(folder)
    assert present["source"] == "rubric.md"
    assert present["items"][0]["text"] == "能指出情景约束"


class _FakeGateway:
    def __init__(self, captured: Dict[str, Any], *, text: str | None = None) -> None:
        self.captured = captured
        self.text = text or json.dumps(
            {
                "suggested_score": 12,
                "max_score": 20,
                "comment": "能指出约束",
                "checks": [{"id": "1", "pass": True, "note": "ok"}],
            },
            ensure_ascii=False,
        )

    def resolve_target(self) -> Target:
        return Target(
            provider="openai",
            mode="openai-chat",
            model="demo-model",
            base_url="http://example.invalid/v1",
            endpoint="/chat/completions",
            headers={"Authorization": "Bearer demo", "Content-Type": "application/json"},
            timeout_sec=(10.0, 120.0),
            retry=1,
        )

    def generate(self, req: Any, allow_fallback: bool = True, target_override: Any = None, **_kwargs: Any):
        self.captured["allow_fallback"] = allow_fallback
        self.captured["target_override"] = target_override
        self.captured["req"] = req
        return UnifiedLLMResponse(text=self.text)


def _write_attempt_with_text(root: Path, *, attempt_id: str = "submission_20260115_000000") -> str:
    attempt_dir = root / "student_submissions" / "HW_1" / "S1" / attempt_id
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "notes.md").write_text("学生写了情景约束和自己的步骤。\n", encoding="utf-8")
    return attempt_id


def test_rubric_suggest_generate_override_is_full_target(tmp_path: Path) -> None:
    attempt_id = _write_attempt_with_text(tmp_path)
    captured: Dict[str, Any] = {}
    result = run_rubric_suggest_job(
        {
            "job_kind": "rubric_suggest",
            "assignment_id": "HW_1",
            "student_id": "S1",
            "attempt_id": attempt_id,
        },
        data_dir=tmp_path,
        gateway=_FakeGateway(captured),
        diag_log=lambda _event, _payload: None,
    )
    override = captured["target_override"]
    assert isinstance(override, dict)
    assert override.get("model") == "demo-model"
    assert override.get("base_url") == "http://example.invalid/v1"
    assert override.get("endpoint") == "/chat/completions"
    assert "headers" in override
    assert override.get("timeout_sec") == 15
    assert captured["allow_fallback"] is False
    assert set(override.keys()) != {"timeout_sec"}
    assert "model" in override and "base_url" in override and "endpoint" in override
    assert result.get("status") == "ready"
    assert result.get("suggested_score") == 12
    assert result.get("source") == "llm"
    saved = json.loads(
        (tmp_path / "student_submissions" / "HW_1" / "S1" / "rubric_suggestion.json").read_text(
            encoding="utf-8"
        )
    )
    assert "official_score" not in saved
    assert saved.get("suggested_score") == 12


def test_rubric_suggest_foreign_attempt_id_does_not_read(tmp_path: Path) -> None:
    legit = _write_attempt_with_text(tmp_path, attempt_id="submission_legit")
    foreign = tmp_path / "student_submissions" / "HW_OTHER" / "S9" / "submission_foreign"
    foreign.mkdir(parents=True, exist_ok=True)
    (foreign / "secret.md").write_text("不该被读到的文本", encoding="utf-8")
    captured: Dict[str, Any] = {}
    logs: List[tuple] = []
    result = run_rubric_suggest_job(
        {
            "job_kind": "rubric_suggest",
            "assignment_id": "HW_1",
            "student_id": "S1",
            "attempt_id": "../HW_OTHER/S9/submission_foreign",
        },
        data_dir=tmp_path,
        gateway=_FakeGateway(captured),
        diag_log=lambda event, payload: logs.append((event, dict(payload or {}))),
    )
    assert result.get("status") == "failed"
    assert captured.get("req") is None
    assert any(event == "assignment.rubric.suggest_failed" for event, _payload in logs)
    saved = json.loads(
        (tmp_path / "student_submissions" / "HW_1" / "S1" / "rubric_suggestion.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved.get("status") == "failed"
    assert legit
    traversal = run_rubric_suggest_job(
        {
            "job_kind": "rubric_suggest",
            "assignment_id": "HW_1",
            "student_id": "S1",
            "attempt_id": "submission_missing",
        },
        data_dir=tmp_path,
        gateway=_FakeGateway(captured),
        diag_log=lambda event, payload: logs.append((event, dict(payload or {}))),
    )
    assert traversal.get("status") == "failed"
    assert captured.get("req") is None
