from __future__ import annotations

import ast
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.grade_submission import get_expected_answer
from services.api.assignment_upload_confirm_service import (
    AssignmentUploadConfirmDeps,
    _finalize_published_from_folder,
)
from services.api.auth_service import AuthPrincipal, reset_current_principal, set_current_principal
from services.api.question_bank_select_service import pick_practice_items


def test_pick_module_does_not_import_llm_gateway() -> None:
    source = Path("services/api/question_bank_select_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("llm_gateway" in name for name in imported)


def test_empty_bank_is_insufficient() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "question_bank").mkdir(parents=True)
        (root / "question_bank" / "questions.csv").write_text(
            "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n",
            encoding="utf-8",
        )
        result = pick_practice_items(
            data_dir=root,
            app_root=root,
            kp_list=["力学"],
            excluded_ids=set(),
            count=3,
        )
        assert result["ok"] is False
        assert result["reason"] == "question_bank_insufficient"


def test_published_assignment_answers_survive_bank_mutation() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        data_dir = root / "data"
        bank = data_dir / "question_bank"
        bank.mkdir(parents=True)
        stem = bank / "q1_stem.md"
        answer = bank / "q1_ans.md"
        stem.write_text("题干", encoding="utf-8")
        answer.write_text("答案：42", encoding="utf-8")
        (bank / "questions.csv").write_text(
            "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
            f"Q1,力学,basic,open,{stem},{answer},bank,\n",
            encoding="utf-8",
        )
        folder = data_dir / "assignments" / "HW_BANK"
        folder.mkdir(parents=True)
        (folder / "questions.csv").write_text(
            "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
            f"Q1,力学,basic,open,{stem},{answer},bank,\n",
            encoding="utf-8",
        )
        (folder / "requirements.json").write_text(
            '{"subject":"物理","topic":"力","grade_level":"初二","class_level":"中等",'
            '"core_concepts":["力","质量","加速度"],"typical_problem":"牛顿",'
            '"misconceptions":["a","b","c","d"],"duration_minutes":40,"preferences":["A基础"]}',
            encoding="utf-8",
        )
        (folder / "meta.json").write_text(
            '{"assignment_id":"HW_BANK","teacher_id":"t_zhang","subject_id":"physics",'
            '"visibility_status":"draft","assignment_kind":"problem_set","content_source":"bank",'
            '"scope":"public","student_ids":[]}',
            encoding="utf-8",
        )

        def _write_json(path: Path, payload: dict) -> None:
            path.write_text(__import__("json").dumps(payload, ensure_ascii=False), encoding="utf-8")

        deps = AssignmentUploadConfirmDeps(
            data_dir=data_dir,
            now_iso=lambda: "2026-02-08T12:00:00",
            discussion_complete_marker="",
            write_upload_job=lambda *_a, **_k: {},
            merge_requirements=lambda base, override, overwrite=True: {**(base or {}), **(override or {})},
            compute_requirements_missing=lambda req, **_k: [],
            write_uploaded_questions=lambda *_a, **_k: [],
            optional_assignment_date=lambda v: None,
            save_assignment_requirements=lambda *_a, **_k: None,
            parse_ids_value=lambda value: value if isinstance(value, list) else [],
            resolve_scope=lambda scope, *_a, **_k: str(scope or "") or "public",
            normalize_due_at=lambda value: str(value or ""),
            compute_expected_students=lambda *_a, **_k: ["S1"],
            atomic_write_json=_write_json,
            copy2=lambda src, dst: dst.write_bytes(src.read_bytes()),
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        try:
            _finalize_published_from_folder("HW_BANK", strict_requirements=True, deps=deps)
        finally:
            reset_current_principal(token)
        answer.write_text("答案：mutated", encoding="utf-8")
        import csv

        with (folder / "questions.csv").open(encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        expected = get_expected_answer(row)
        assert "42" in expected
        assert "mutated" not in expected
