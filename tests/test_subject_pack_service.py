from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from services.api import subject_pack_service as svc


def _write_pack(
    pack_dir: Path,
    *,
    subject_id: str,
    display_name: str,
    grader: str = "none",
    student_overlay: str,
    teacher_overlay: str = "",
    adapter_source: str | None = None,
) -> None:
    prompts_dir = pack_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "student_overlay.md").write_text(student_overlay, encoding="utf-8")
    (prompts_dir / "teacher_overlay.md").write_text(teacher_overlay, encoding="utf-8")
    manifest: dict[str, Any] = {
        "subject_id": subject_id,
        "display_name": display_name,
        "schema_version": 1,
        "grader": grader,
        "prompts": {
            "student_overlay": "prompts/student_overlay.md",
            "teacher_overlay": "prompts/teacher_overlay.md",
        },
    }
    (pack_dir / "pack.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    if adapter_source is not None:
        grader_dir = pack_dir / "grader"
        grader_dir.mkdir(parents=True, exist_ok=True)
        (grader_dir / "adapter.py").write_text(adapter_source, encoding="utf-8")


@pytest.fixture
def packs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "subjects"
    _write_pack(
        root / "generic",
        subject_id="generic",
        display_name="通用",
        student_overlay="【学科 overlay：通用】中性陪练，无学科公式包。",
        teacher_overlay="【学科 overlay：通用】中性布置检查，不套用其他学科公式。",
    )
    _write_pack(
        root / "physics",
        subject_id="physics",
        display_name="物理",
        student_overlay="【学科 overlay：物理】使用 SI 单位，禁止如图。",
        teacher_overlay="【学科 overlay：物理】物理作业场景必须文字自包含。",
    )
    monkeypatch.setattr(svc, "PACKS_DIR", root)
    svc.clear_pack_cache()
    return root


def test_load_pack_uses_generic_when_subject_missing(packs_dir: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    svc._fallback_logger = lambda event, payload: events.append((event, payload))
    try:
        pack = svc.load_pack("math")
    finally:
        svc._fallback_logger = None

    assert pack.subject_id == "generic"
    assert pack.display_name == "通用"
    assert pack.fallback is True
    assert pack.requested_subject_id == "math"
    assert pack.grader == "none"
    assert events == [
        ("subject_pack_fallback", {"subject_id": "math", "pack": "generic"}),
    ]
    overlay = svc.student_prompt_overlay("math")
    assert "【学科 overlay：通用】" in overlay
    assert "【学科 overlay：物理】" not in overlay
    assert "公式包" in overlay


def test_load_pack_never_falls_back_to_physics_when_physics_pack_missing(
    packs_dir: Path,
) -> None:
    import shutil

    shutil.rmtree(packs_dir / "physics")
    svc.clear_pack_cache()
    events: list[tuple[str, dict[str, Any]]] = []
    svc._fallback_logger = lambda event, payload: events.append((event, payload))
    try:
        pack = svc.load_pack("physics")
    finally:
        svc._fallback_logger = None

    assert pack.subject_id == "generic"
    assert pack.fallback is True
    assert pack.requested_subject_id == "physics"
    assert events == [
        ("subject_pack_fallback", {"subject_id": "physics", "pack": "generic"}),
    ]
    assert "【学科 overlay：物理】" not in svc.student_prompt_overlay("physics")


def test_load_pack_physics_when_present(packs_dir: Path) -> None:
    pack = svc.load_pack("physics")
    assert pack.subject_id == "physics"
    assert pack.fallback is False
    assert "【学科 overlay：物理】" in svc.student_prompt_overlay("physics")
    assert svc.grade_adapter("physics") is None


def test_load_pack_empty_or_generic_does_not_log_fallback(packs_dir: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    svc._fallback_logger = lambda event, payload: events.append((event, payload))
    try:
        empty = svc.load_pack("")
        generic = svc.load_pack("generic")
        none_id = svc.load_pack(None)
    finally:
        svc._fallback_logger = None

    assert empty.subject_id == "generic"
    assert generic.subject_id == "generic"
    assert none_id.subject_id == "generic"
    assert empty.fallback is False
    assert generic.fallback is False
    assert events == []


def test_load_pack_rejects_path_traversal_as_generic_fallback(packs_dir: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    svc._fallback_logger = lambda event, payload: events.append((event, payload))
    try:
        pack = svc.load_pack("../physics")
    finally:
        svc._fallback_logger = None

    assert pack.subject_id == "generic"
    assert pack.fallback is True
    assert events[0][0] == "subject_pack_fallback"
    assert events[0][1]["pack"] == "generic"


def test_missing_generic_pack_is_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "subjects"
    root.mkdir()
    monkeypatch.setattr(svc, "PACKS_DIR", root)
    svc.clear_pack_cache()
    with pytest.raises(svc.SubjectPackError):
        svc.load_pack("math")


def test_grade_adapter_none_for_generic(packs_dir: Path) -> None:
    assert svc.grade_adapter("generic") is None
    assert svc.grade_adapter("math") is None


def test_grade_adapter_optional_python_adapter(packs_dir: Path) -> None:
    _write_pack(
        packs_dir / "math",
        subject_id="math",
        display_name="数学",
        grader="python_adapter",
        student_overlay="【学科 overlay：数学】",
        adapter_source=(
            "def score_item(*, question, student_text):\n"
            "    return {'score': 1.0, 'confidence': 0.9, 'status': 'matched', 'reason': 'math_adapter'}\n"
        ),
    )
    svc.clear_pack_cache()
    adapter = svc.grade_adapter("math")
    assert adapter is not None
    result = adapter.score_item(question={"question_id": "Q1"}, student_text="42")
    assert result["status"] == "matched"
    assert result["reason"] == "math_adapter"
    assert result["score"] == 1.0


def test_repo_generic_and_physics_packs_exist() -> None:
    svc.clear_pack_cache()
    generic = svc.load_pack("generic")
    physics = svc.load_pack("physics")
    assert generic.subject_id == "generic"
    assert generic.grader == "none"
    assert physics.subject_id == "physics"
    assert "【学科 overlay：通用】" in svc.student_prompt_overlay(None)
    assert "【学科 overlay：物理】" in svc.student_prompt_overlay("physics")
    assert svc.grade_adapter("generic") is None
