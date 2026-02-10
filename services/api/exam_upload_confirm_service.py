from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


class ExamUploadConfirmError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def _resolve_exam_dir(data_dir: Path, exam_id: str) -> Path:
    root = (data_dir / "exams").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        raise ExamUploadConfirmError(400, "exam_id missing")
    target = (root / eid).resolve()
    if target != root and root not in target.parents:
        raise ExamUploadConfirmError(400, "invalid exam_id")
    return target


def _resolve_analysis_dir(data_dir: Path, exam_id: str) -> Path:
    root = (data_dir / "analysis").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        raise ExamUploadConfirmError(400, "exam_id missing")
    target = (root / eid).resolve()
    if target != root and root not in target.parents:
        raise ExamUploadConfirmError(400, "invalid exam_id")
    return target


@dataclass(frozen=True)
class ExamUploadConfirmDeps:
    app_root: Path
    data_dir: Path
    now_iso: Callable[[], str]
    write_exam_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    load_exam_draft_override: Callable[[Path], Dict[str, Any]]
    parse_exam_answer_key_text: Callable[[str], Any]
    write_exam_questions_csv: Callable[[Path, List[Dict[str, Any]], Optional[Dict[str, float]]], None]
    write_exam_answers_csv: Callable[[Path, List[Dict[str, Any]]], None]
    load_exam_answer_key_from_csv: Callable[[Path], Dict[str, str]]
    ensure_questions_max_score: Callable[[Path, Iterable[str], float], List[str]]
    apply_answer_key_to_responses_csv: Callable[[Path, Path, Path, Path], Dict[str, Any]]
    run_script: Callable[[List[str]], Any]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]
    copy2: Callable[[Path, Path], Any]


def _to_rel(path: Path, app_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(app_root.resolve()))
    except Exception:
        return str(path.resolve())


def _copy_if_exists(src: Path, dst: Path, copy2: Callable[[Path, Path], Any]) -> None:
    if src.exists():
        copy2(src, dst)


def confirm_exam_upload(
    job_id: str,
    job: Dict[str, Any],
    job_dir: Path,
    deps: ExamUploadConfirmDeps,
) -> Dict[str, Any]:
    deps.write_exam_job(job_id, {"status": "confirming", "step": "start", "progress": 5})

    parsed_path = job_dir / "parsed.json"
    if not parsed_path.exists():
        deps.write_exam_job(job_id, {"status": "failed", "error": "parsed result missing", "step": "failed"})
        raise ExamUploadConfirmError(400, "parsed result missing")
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))

    override = deps.load_exam_draft_override(job_dir)
    parsed_score_schema = parsed.get("score_schema") if isinstance(parsed.get("score_schema"), dict) else {}
    override_score_schema = override.get("score_schema") if isinstance(override.get("score_schema"), dict) else {}
    merged_score_schema = {**parsed_score_schema, **override_score_schema} if isinstance(parsed_score_schema, dict) else override_score_schema
    needs_confirm = bool(merged_score_schema.get("needs_confirm"))
    selected_candidate_id = str(
        (
            ((merged_score_schema.get("subject") or {}).get("selected_candidate_id")
            if isinstance(merged_score_schema.get("subject"), dict)
            else merged_score_schema.get("selected_candidate_id"))
        )
        or ""
    ).strip()
    subject_info = merged_score_schema.get("subject") if isinstance(merged_score_schema.get("subject"), dict) else {}
    selected_candidate_available = bool(subject_info.get("selected_candidate_available", True))
    selection_error = str(subject_info.get("selection_error") or "").strip()
    candidate_selection_valid = bool((not selected_candidate_id) or (selected_candidate_available and not selection_error))
    confirmed_mapping = bool((selected_candidate_id and candidate_selection_valid) or merged_score_schema.get("confirm"))
    if needs_confirm and not confirmed_mapping:
        deps.write_exam_job(job_id, {"status": "done", "step": "await_confirm", "progress": 100, "needs_confirm": True})
        raise ExamUploadConfirmError(
            400,
            {
                "error": "score_schema_confirm_required",
                "message": "成绩映射置信度不足，请先在草稿中确认物理分映射后再创建考试。",
                "needs_confirm": True,
            },
        )
    exam_id = str(parsed.get("exam_id") or job.get("exam_id") or "").strip()
    if not exam_id:
        raise ExamUploadConfirmError(400, "exam_id missing")

    meta = parsed.get("meta") or {}
    if isinstance(override.get("meta"), dict) and override.get("meta"):
        meta = {**meta, **override.get("meta")}
    questions_override = override.get("questions") if isinstance(override.get("questions"), list) else None

    try:
        exam_dir = _resolve_exam_dir(deps.data_dir, exam_id)
    except ExamUploadConfirmError as exc:
        deps.write_exam_job(job_id, {"status": "failed", "error": str(exc.detail), "step": "failed"})
        raise
    manifest_path = exam_dir / "manifest.json"
    if manifest_path.exists():
        deps.write_exam_job(job_id, {"status": "confirmed", "step": "confirmed", "progress": 100})
        raise ExamUploadConfirmError(409, "exam already exists")
    exam_dir.mkdir(parents=True, exist_ok=True)

    deps.write_exam_job(job_id, {"step": "copy_files", "progress": 25})
    dest_paper_dir = exam_dir / "paper"
    dest_scores_dir = exam_dir / "scores"
    dest_answers_dir = exam_dir / "answers"
    dest_derived_dir = exam_dir / "derived"
    dest_paper_dir.mkdir(parents=True, exist_ok=True)
    dest_scores_dir.mkdir(parents=True, exist_ok=True)
    dest_answers_dir.mkdir(parents=True, exist_ok=True)
    dest_derived_dir.mkdir(parents=True, exist_ok=True)
    for fname in job.get("paper_files") or []:
        _copy_if_exists(job_dir / "paper" / str(fname), dest_paper_dir / str(fname), deps.copy2)
    for fname in job.get("score_files") or []:
        _copy_if_exists(job_dir / "scores" / str(fname), dest_scores_dir / str(fname), deps.copy2)
    for fname in job.get("answer_files") or []:
        _copy_if_exists(job_dir / "answers" / str(fname), dest_answers_dir / str(fname), deps.copy2)

    deps.write_exam_job(job_id, {"step": "write_derived", "progress": 50})
    src_unscored = job_dir / "derived" / "responses_unscored.csv"
    src_responses = job_dir / "derived" / "responses_scored.csv"
    src_questions = job_dir / "derived" / "questions.csv"
    src_answers = job_dir / "derived" / "answers.csv"
    if not src_responses.exists():
        deps.write_exam_job(job_id, {"status": "failed", "error": "responses missing", "step": "failed"})
        raise ExamUploadConfirmError(400, "responses missing")

    if src_unscored.exists():
        deps.copy2(src_unscored, dest_derived_dir / "responses_unscored.csv")
    else:
        deps.copy2(src_responses, dest_derived_dir / "responses_unscored.csv")
    _copy_if_exists(src_questions, dest_derived_dir / "questions.csv", deps.copy2)
    _copy_if_exists(src_answers, dest_derived_dir / "answers.csv", deps.copy2)
    if questions_override:
        max_scores = None
        try:
            max_scores = {
                str(question.get("question_id")): float(question.get("max_score"))
                for question in questions_override
                if question.get("max_score") is not None
            }
        except Exception:
            max_scores = None
        deps.write_exam_questions_csv(dest_derived_dir / "questions.csv", questions_override, max_scores=max_scores)

    answer_key_text = str(override.get("answer_key_text") or "").strip()
    dest_unscored = dest_derived_dir / "responses_unscored.csv"
    dest_answers = dest_derived_dir / "answers.csv"
    dest_questions = dest_derived_dir / "questions.csv"
    dest_scored = dest_derived_dir / "responses_scored.csv"
    if answer_key_text:
        try:
            override_answers, _warnings = deps.parse_exam_answer_key_text(answer_key_text)
            if override_answers:
                deps.write_exam_answers_csv(dest_answers, override_answers)
            else:
                if dest_answers.exists():
                    dest_answers.unlink()
        except Exception:
            pass

    if dest_unscored.exists() and dest_answers.exists() and dest_questions.exists():
        try:
            try:
                answers = deps.load_exam_answer_key_from_csv(dest_answers)
                deps.ensure_questions_max_score(dest_questions, answers.keys(), default_score=1.0)
            except Exception:
                pass
            deps.apply_answer_key_to_responses_csv(dest_unscored, dest_answers, dest_questions, dest_scored)
        except Exception:
            if src_responses.exists():
                deps.copy2(src_responses, dest_scored)
            else:
                deps.copy2(dest_unscored, dest_scored)
    else:
        deps.copy2(src_responses, dest_scored)

    deps.write_exam_job(job_id, {"step": "analysis", "progress": 70})
    analysis_dir = _resolve_analysis_dir(deps.data_dir, exam_id)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    draft_json = analysis_dir / "draft.json"
    draft_md = analysis_dir / "draft.md"
    try:
        script = deps.app_root / "skills" / "physics-teacher-ops" / "scripts" / "compute_exam_metrics.py"
        cmd = [
            "python3",
            str(script),
            "--exam-id",
            exam_id,
            "--responses",
            str(dest_derived_dir / "responses_scored.csv"),
            "--questions",
            str(dest_derived_dir / "questions.csv"),
            "--out-json",
            str(draft_json),
            "--out-md",
            str(draft_md),
        ]
        deps.run_script(cmd)
    except Exception as exc:
        deps.diag_log("exam_upload.analysis_failed", {"exam_id": exam_id, "error": str(exc)[:200]})

    deps.write_exam_job(job_id, {"step": "manifest", "progress": 90})
    manifest = {
        "exam_id": exam_id,
        "generated_at": deps.now_iso(),
        "meta": meta,
        "files": {
            "responses_scored": _to_rel(dest_derived_dir / "responses_scored.csv", deps.app_root),
            "responses_unscored": _to_rel(dest_derived_dir / "responses_unscored.csv", deps.app_root)
            if (dest_derived_dir / "responses_unscored.csv").exists()
            else "",
            "questions": _to_rel(dest_derived_dir / "questions.csv", deps.app_root),
            "answers": _to_rel(dest_derived_dir / "answers.csv", deps.app_root)
            if (dest_derived_dir / "answers.csv").exists()
            else "",
            "analysis_draft_json": _to_rel(draft_json, deps.app_root) if draft_json.exists() else "",
            "analysis_draft_md": _to_rel(draft_md, deps.app_root) if draft_md.exists() else "",
        },
        "counts": parsed.get("counts") or {},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    deps.write_exam_job(job_id, {"status": "confirmed", "step": "confirmed", "progress": 100, "exam_id": exam_id})
    return {"ok": True, "exam_id": exam_id, "status": "confirmed", "message": "考试已创建。"}
