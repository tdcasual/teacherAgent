from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_draft_from_bank_service import (
    AssignmentDraftFromBankDeps,
    AssignmentDraftFromBankError,
    create_assignment_draft_from_bank,
)
from services.api.assignment_requirements_service import compute_requirements_missing
from services.api.assignment_upload_confirm_service import (
    AssignmentUploadConfirmDeps,
    _finalize_published_from_folder,
)
from services.api.auth_service import AuthPrincipal, reset_current_principal, set_current_principal


def _from_bank_deps(root: Path) -> AssignmentDraftFromBankDeps:
    return AssignmentDraftFromBankDeps(
        data_dir=root / "data",
        app_root=root,
        optional_assignment_date=lambda value: str(value).strip() if str(value or "").strip() else None,
        parse_ids_value=lambda value: [p for p in str(value or "").split(",") if p.strip()]
        if not isinstance(value, list)
        else value,
        resolve_scope=lambda scope, student_ids, class_name: str(scope or "") or "public",
        normalize_due_at=lambda value: str(value or ""),
        postprocess_assignment_meta=lambda *_a, **_k: None,
        diag_log=lambda *_a, **_k: None,
        now_iso=lambda: "2026-02-08T12:00:00",
    )


def _seed_bank(root: Path) -> None:
    bank = root / "data" / "question_bank"
    bank.mkdir(parents=True)
    stem = bank / "s.md"
    ans = bank / "a.md"
    stem.write_text("stem", encoding="utf-8")
    ans.write_text("答案：ok", encoding="utf-8")
    (bank / "questions.csv").write_text(
        "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
        f"Q1,力学,basic,open,{stem},{ans},bank,\n",
        encoding="utf-8",
    )


def test_from_bank_confirm_writes_expected_students() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _seed_bank(root)
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        try:
            created = create_assignment_draft_from_bank(
                assignment_id="HW_BANK",
                subject_id="physics",
                kp="力学",
                count=1,
                deps=_from_bank_deps(root),
            )
            assert created.get("ok")
            req = {
                "subject": "物理",
                "topic": "力",
                "grade_level": "初二",
                "class_level": "中等",
                "core_concepts": ["力", "质量", "加速度"],
                "typical_problem": "牛顿",
                "misconceptions": ["a", "b", "c", "d"],
                "duration_minutes": 40,
                "preferences": ["A基础"],
            }
            folder = root / "data" / "assignments" / "HW_BANK"
            (folder / "requirements.json").write_text(
                json.dumps(req, ensure_ascii=False), encoding="utf-8"
            )

            def _write_json(path: Path, payload: dict) -> None:
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            confirm_deps = AssignmentUploadConfirmDeps(
                data_dir=root / "data",
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
                compute_expected_students=lambda *_a, **_k: ["S1", "S2"],
                atomic_write_json=_write_json,
                copy2=lambda src, dst: dst.write_bytes(src.read_bytes()) if src.exists() else None,
            )
            _finalize_published_from_folder("HW_BANK", strict_requirements=True, deps=confirm_deps)
        finally:
            reset_current_principal(token)
        meta = json.loads((root / "data" / "assignments" / "HW_BANK" / "meta.json").read_text(encoding="utf-8"))
        assert meta.get("expected_students") == ["S1", "S2"]
        assert meta.get("visibility_status") == "published"


def test_bank_requires_problem_set() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        folder = root / "data" / "assignments" / "HW_SCEN"
        folder.mkdir(parents=True)
        (folder / "meta.json").write_text(
            json.dumps(
                {
                    "assignment_id": "HW_SCEN",
                    "teacher_id": "t_zhang",
                    "subject_id": "physics",
                    "visibility_status": "draft",
                    "assignment_kind": "scenario",
                    "content_source": "bank",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (folder / "requirements.json").write_text(
            json.dumps({"subject": "物理", "topic": "情景", "grade_level": "初二", "brief": "b"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (folder / "questions.csv").write_text(
            "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\nQ1,k,basic,open,,,,\n",
            encoding="utf-8",
        )

        def _write_json(path: Path, payload: dict) -> None:
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        deps = AssignmentUploadConfirmDeps(
            data_dir=root / "data",
            now_iso=lambda: "2026-02-08T12:00:00",
            discussion_complete_marker="",
            write_upload_job=lambda *_a, **_k: {},
            merge_requirements=lambda base, override, overwrite=True: {**(base or {}), **(override or {})},
            compute_requirements_missing=lambda req, **_k: [],
            write_uploaded_questions=lambda *_a, **_k: [],
            optional_assignment_date=lambda v: None,
            save_assignment_requirements=lambda *_a, **_k: None,
            parse_ids_value=lambda value: [],
            resolve_scope=lambda *_a, **_k: "public",
            normalize_due_at=lambda value: "",
            compute_expected_students=lambda *_a, **_k: [],
            atomic_write_json=_write_json,
            copy2=lambda src, dst: None,
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        try:
            from services.api.assignment_upload_confirm_service import AssignmentUploadConfirmError

            try:
                _finalize_published_from_folder("HW_SCEN", strict_requirements=True, deps=deps)
                raise AssertionError("expected bank_requires_problem_set")
            except AssignmentUploadConfirmError as exc:
                assert exc.status_code == 400
                assert exc.detail == "bank_requires_problem_set"
        finally:
            reset_current_principal(token)


def test_from_bank_conflict_if_not_own_draft() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _seed_bank(root)
        folder = root / "data" / "assignments" / "HW_TAKEN"
        folder.mkdir(parents=True)
        (folder / "meta.json").write_text(
            json.dumps(
                {
                    "assignment_id": "HW_TAKEN",
                    "teacher_id": "t_other",
                    "visibility_status": "draft",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        try:
            try:
                create_assignment_draft_from_bank(
                    assignment_id="HW_TAKEN",
                    subject_id="physics",
                    kp="力学",
                    deps=_from_bank_deps(root),
                )
                raise AssertionError("expected conflict")
            except AssignmentDraftFromBankError as exc:
                assert exc.status_code == 409
                assert exc.detail == "assignment already exists"
        finally:
            reset_current_principal(token)


def test_from_bank_requirements_missing_is_computed() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _seed_bank(root)
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        try:
            created = create_assignment_draft_from_bank(
                assignment_id="HW_BANK_MISS",
                subject_id="physics",
                kp="力学",
                count=1,
                deps=_from_bank_deps(root),
            )
        finally:
            reset_current_principal(token)
        assert created.get("ok")
        assert created["draft"]["requirements_missing"] == compute_requirements_missing(
            {}, assignment_kind="problem_set"
        )
        assert "subject" in created["draft"]["requirements_missing"]
        assert "preferences" in created["draft"]["requirements_missing"]


def test_from_bank_rejects_unsafe_assignment_id() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _seed_bank(root)
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        try:
            for aid in (".", "../escape", "a/b"):
                try:
                    create_assignment_draft_from_bank(
                        assignment_id=aid,
                        subject_id="physics",
                        kp="力学",
                        deps=_from_bank_deps(root),
                    )
                    raise AssertionError(f"expected invalid assignment_id for {aid!r}")
                except AssignmentDraftFromBankError as exc:
                    assert exc.status_code == 400
                    assert exc.detail == "invalid assignment_id"
        finally:
            reset_current_principal(token)
