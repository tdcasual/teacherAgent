from __future__ import annotations

import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import HTTPException

from services.api.assignment_submission_attempt_service import (
    AssignmentSubmissionAttemptDeps,
    list_submission_attempts,
)
from services.api.student_practice_service import (
    StudentPracticeDeps,
    StudentPracticeError,
    recommend_practice,
    submit_practice,
)


def _deps(root: Path, **overrides) -> StudentPracticeDeps:
    fields = dict(
        data_dir=root,
        app_root=root,
        student_submissions_dir=root / "student_submissions",
        uploads_dir=root / "uploads",
        run_script=lambda _args: "ok",
        diag_log=lambda _event, _payload: None,
        save_upload_file=_save_upload,
        sanitize_filename=lambda name: Path(str(name or "")).name,
        authorize_student_submit=lambda *_a, **_k: None,
    )
    fields.update(overrides)
    return StudentPracticeDeps(**fields)


async def _save_upload(upload, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = getattr(upload, "content", b"")
    dest.write_bytes(payload)
    return len(payload)


class _Upload:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content = content

    async def read(self, size: int = -1) -> bytes:
        if size is None or int(size) < 0:
            raise AssertionError("full read() is forbidden")
        return self.content[: int(size)] if int(size) else b""


def _write_assignment(root: Path, assignment_id: str, *, kind: str = "problem_set", allow_practice=True) -> None:
    folder = root / "assignments" / assignment_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "questions.csv").write_text(
        "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\nHWQ1,力学,basic,open,,,,\n",
        encoding="utf-8",
    )
    (folder / "requirements.json").write_text(
        json.dumps({"core_concepts": ["力学"]}),
        encoding="utf-8",
    )
    (folder / "meta.json").write_text(
        json.dumps(
            {
                "assignment_id": assignment_id,
                "assignment_kind": kind,
                "teacher_id": "t_zhang",
                "subject_id": "physics",
                "visibility_status": "published",
                "completion_policy": {"allow_practice": allow_practice},
            }
        ),
        encoding="utf-8",
    )


def _write_homework(root: Path, assignment_id: str, student_id: str) -> None:
    attempt = root / "student_submissions" / assignment_id / student_id / "submission_20260101_000000"
    attempt.mkdir(parents=True, exist_ok=True)
    (attempt / "grading_report.json").write_text(
        json.dumps({"graded_total": 1, "correct": 1, "items": [{"question_id": "HWQ1", "status": "matched"}]}),
        encoding="utf-8",
    )


def _write_bank(root: Path, *, rows: str | None = None) -> None:
    bank = root / "question_bank"
    bank.mkdir(parents=True, exist_ok=True)
    stem = bank / "p1_stem.md"
    answer = bank / "p1_ans.md"
    stem.write_text("补练题干", encoding="utf-8")
    answer.write_text("答案：1", encoding="utf-8")
    if rows is None:
        rows = (
            "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
            f"P1,力学,basic,open,{stem},{answer},bank,\n"
        )
    (bank / "questions.csv").write_text(rows, encoding="utf-8")


def test_practice_module_does_not_import_llm_or_generate() -> None:
    source = Path("services/api/student_practice_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    joined = " ".join(imported)
    assert "llm_gateway" not in joined
    assert "select_practice" not in joined
    assert "make_generated" not in source


def test_recommend_requires_homework_submitted() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_1")
        _write_bank(root)
        try:
            recommend_practice("HW_1", student_id="S1", deps=_deps(root))
            raise AssertionError("expected homework_not_submitted")
        except StudentPracticeError as exc:
            assert exc.status_code == 409
            assert exc.detail == "homework_not_submitted"


def test_recommend_rejects_non_problem_set() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_SCEN", kind="scenario")
        _write_homework(root, "HW_SCEN", "S1")
        _write_bank(root)
        try:
            recommend_practice("HW_SCEN", student_id="S1", deps=_deps(root))
            raise AssertionError("expected practice_not_applicable")
        except StudentPracticeError as exc:
            assert exc.status_code == 409
            assert exc.detail == "practice_not_applicable"
            assert not (root / "student_submissions" / "HW_SCEN" / "S1" / "bank_miss.json").exists()


def test_bank_miss_persists_marker_file() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_1")
        _write_homework(root, "HW_1", "S1")
        _write_bank(
            root,
            rows="question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n",
        )
        try:
            recommend_practice("HW_1", student_id="S1", deps=_deps(root))
            raise AssertionError("expected question_bank_insufficient")
        except StudentPracticeError as exc:
            assert exc.status_code == 409
            assert exc.detail == "question_bank_insufficient"
        marker = root / "student_submissions" / "HW_1" / "S1" / "bank_miss.json"
        assert marker.is_file()
        payload = json.loads(marker.read_text(encoding="utf-8"))
        assert payload["reason"] == "question_bank_insufficient"


@pytest.mark.anyio
async def test_practice_submit_does_not_count_as_homework_attempt() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_1")
        _write_homework(root, "HW_1", "S1")
        _write_bank(root)
        payload = recommend_practice("HW_1", student_id="S1", deps=_deps(root))
        practice_id = payload["practice_id"]
        attempt_deps = AssignmentSubmissionAttemptDeps(
            student_submissions_dir=root / "student_submissions",
            grade_count_conf_threshold=0.6,
        )
        before = list_submission_attempts("HW_1", "S1", deps=attempt_deps)
        practice_dir = root / "student_submissions" / "HW_1" / "S1" / practice_id

        def _run(args):
            assert "--attempt-dir" in args
            assert "--skip-profile-update" in args
            (practice_dir / "grading_report.json").write_text(
                json.dumps(
                    {
                        "graded_total": 1,
                        "correct": 1,
                        "items": [{"question_id": "P1", "kp_id": "力学", "status": "matched"}],
                    }
                ),
                encoding="utf-8",
            )
            return "ok"

        result = await submit_practice(
            "HW_1",
            practice_id,
            student_id="S1",
            files=[_Upload(filename="p1.pdf", content=b"1")],
            deps=_deps(root, run_script=_run),
        )
        assert result["ok"] is True
        assert result["submitted"] is True
        assert result["official_score"] is None
        after = list_submission_attempts("HW_1", "S1", deps=attempt_deps)
        assert len(after) == len(before)
        meta = json.loads((practice_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["status"] == "submitted"


@pytest.mark.anyio
async def test_practice_submit_deletes_leak_and_returns_500() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_1")
        _write_homework(root, "HW_1", "S1")
        _write_bank(root)
        payload = recommend_practice("HW_1", student_id="S1", deps=_deps(root))
        practice_id = payload["practice_id"]

        def _run(_args):
            leaked = root / "student_submissions" / "HW_1" / "S1" / "submission_leaked"
            leaked.mkdir(parents=True, exist_ok=True)
            (leaked / "grading_report.json").write_text("{}", encoding="utf-8")
            return "ok"

        try:
            await submit_practice(
                "HW_1",
                practice_id,
                student_id="S1",
                files=[_Upload(filename="p1.pdf", content=b"1")],
                deps=_deps(root, run_script=_run),
            )
            raise AssertionError("expected leak")
        except StudentPracticeError as exc:
            assert exc.status_code == 500
            assert exc.detail == "attempt_dir_leak"
        assert not (root / "student_submissions" / "HW_1" / "S1" / "submission_leaked").exists()


@pytest.mark.anyio
async def test_practice_ungraded_stays_in_practice_dir() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_1")
        _write_homework(root, "HW_1", "S1")
        _write_bank(root)
        payload = recommend_practice("HW_1", student_id="S1", deps=_deps(root))
        practice_id = payload["practice_id"]

        def _boom(_args):
            raise HTTPException(status_code=500, detail="ocr_utils not available")

        result = await submit_practice(
            "HW_1",
            practice_id,
            student_id="S1",
            files=[_Upload(filename="p1.pdf", content=b"1")],
            deps=_deps(root, run_script=_boom),
        )
        assert result["ok"] is True
        report = json.loads(
            (root / "student_submissions" / "HW_1" / "S1" / practice_id / "grading_report.json").read_text(
                encoding="utf-8"
            )
        )
        assert report["items"][0]["status"] == "ungraded"
        attempts = list_submission_attempts(
            "HW_1",
            "S1",
            deps=AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.6,
            ),
        )
        assert len(attempts) == 1
