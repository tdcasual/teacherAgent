from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

_log = logging.getLogger(__name__)


def _as_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


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


@dataclass(frozen=True)
class ExamDerivedFiles:
    unscored: Path
    questions: Path
    answers: Path
    scored: Path


def _to_rel(path: Path, app_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(app_root.resolve()))
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return str(path.resolve())


def _copy_if_exists(src: Path, dst: Path, copy2: Callable[[Path, Path], Any]) -> None:
    if src.exists():
        copy2(src, dst)


def _derived_files(base_dir: Path) -> ExamDerivedFiles:
    return ExamDerivedFiles(
        unscored=base_dir / "responses_unscored.csv",
        questions=base_dir / "questions.csv",
        answers=base_dir / "answers.csv",
        scored=base_dir / "responses_scored.csv",
    )


def _load_parsed_result(job_id: str, job_dir: Path, deps: ExamUploadConfirmDeps) -> Dict[str, Any]:
    parsed_path = job_dir / "parsed.json"
    if not parsed_path.exists():
        deps.write_exam_job(job_id, {"status": "failed", "error": "parsed result missing", "step": "failed"})
        raise ExamUploadConfirmError(400, "parsed result missing")
    return _as_dict(json.loads(parsed_path.read_text(encoding="utf-8")))


def _merged_score_schema(parsed: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    return {**_as_dict(parsed.get("score_schema")), **_as_dict(override.get("score_schema"))}


def _score_schema_mapping_confirmed(merged_score_schema: Dict[str, Any]) -> bool:
    subject_info = _as_dict(merged_score_schema.get("subject"))
    selected_candidate_id = str(
        (subject_info.get("selected_candidate_id") or merged_score_schema.get("selected_candidate_id")) or ""
    ).strip()
    selected_candidate_available = bool(subject_info.get("selected_candidate_available", True))
    selection_error = str(subject_info.get("selection_error") or "").strip()
    candidate_selection_valid = bool((not selected_candidate_id) or (selected_candidate_available and not selection_error))
    return bool((selected_candidate_id and candidate_selection_valid) or merged_score_schema.get("confirm"))


def _require_confirmed_mapping(job_id: str, merged_score_schema: Dict[str, Any], deps: ExamUploadConfirmDeps) -> None:
    if not merged_score_schema.get("needs_confirm"):
        return
    if _score_schema_mapping_confirmed(merged_score_schema):
        return
    deps.write_exam_job(job_id, {"status": "done", "step": "await_confirm", "progress": 100, "needs_confirm": True})
    raise ExamUploadConfirmError(
        400,
        {
            "error": "score_schema_confirm_required",
            "message": "成绩映射置信度不足，请先在草稿中确认物理分映射后再创建考试。",
            "needs_confirm": True,
        },
    )


def _resolve_exam_id(parsed: Dict[str, Any], job: Dict[str, Any]) -> str:
    exam_id = str(parsed.get("exam_id") or job.get("exam_id") or "").strip()
    if not exam_id:
        raise ExamUploadConfirmError(400, "exam_id missing")
    return exam_id


def _merge_meta(parsed: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    meta = _as_dict(parsed.get("meta"))
    override_meta = _as_dict(override.get("meta"))
    return {**meta, **override_meta} if override_meta else meta


def _questions_override(override: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    questions = override.get("questions")
    return questions if isinstance(questions, list) else None


def _prepare_exam_dir(job_id: str, exam_id: str, deps: ExamUploadConfirmDeps) -> tuple[Path, Path]:
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
    return exam_dir, manifest_path


def _init_exam_subdirs(exam_dir: Path) -> tuple[Path, Path, Path, Path]:
    dest_paper_dir = exam_dir / "paper"
    dest_scores_dir = exam_dir / "scores"
    dest_answers_dir = exam_dir / "answers"
    dest_derived_dir = exam_dir / "derived"
    for path in (dest_paper_dir, dest_scores_dir, dest_answers_dir, dest_derived_dir):
        path.mkdir(parents=True, exist_ok=True)
    return dest_paper_dir, dest_scores_dir, dest_answers_dir, dest_derived_dir


def _copy_named_files(job_dir: Path, src_folder: str, filenames: Any, dest_dir: Path, deps: ExamUploadConfirmDeps) -> None:
    for fname in filenames or []:
        _copy_if_exists(job_dir / src_folder / str(fname), dest_dir / str(fname), deps.copy2)


def _copy_upload_files(job: Dict[str, Any], job_dir: Path, exam_dir: Path, deps: ExamUploadConfirmDeps) -> Path:
    dest_paper_dir, dest_scores_dir, dest_answers_dir, dest_derived_dir = _init_exam_subdirs(exam_dir)
    _copy_named_files(job_dir, "paper", job.get("paper_files"), dest_paper_dir, deps)
    _copy_named_files(job_dir, "scores", job.get("score_files"), dest_scores_dir, deps)
    _copy_named_files(job_dir, "answers", job.get("answer_files"), dest_answers_dir, deps)
    return dest_derived_dir


def _build_question_max_scores(questions_override: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    try:
        return {
            str(question.get("question_id")): float(question.get("max_score"))
            for question in questions_override
            if question.get("max_score") is not None
        }
    except Exception:
        _log.warning("max_scores build failed from questions_override", exc_info=True)
        return None


def _copy_derived_inputs(src_files: ExamDerivedFiles, dest_files: ExamDerivedFiles, deps: ExamUploadConfirmDeps) -> None:
    if src_files.unscored.exists():
        deps.copy2(src_files.unscored, dest_files.unscored)
    else:
        deps.copy2(src_files.scored, dest_files.unscored)
    _copy_if_exists(src_files.questions, dest_files.questions, deps.copy2)
    _copy_if_exists(src_files.answers, dest_files.answers, deps.copy2)


def _apply_questions_override(
    dest_questions: Path,
    questions_override: Optional[List[Dict[str, Any]]],
    deps: ExamUploadConfirmDeps,
) -> None:
    if not questions_override:
        return
    deps.write_exam_questions_csv(dest_questions, questions_override, _build_question_max_scores(questions_override))


def _apply_answer_key_override(dest_answers: Path, answer_key_text: str, deps: ExamUploadConfirmDeps) -> None:
    if not answer_key_text:
        return
    try:
        override_answers, _warnings = deps.parse_exam_answer_key_text(answer_key_text)
        if override_answers:
            deps.write_exam_answers_csv(dest_answers, override_answers)
        elif dest_answers.exists():
            dest_answers.unlink()
    except Exception:
        _log.warning("answer key override parse/write failed", exc_info=True)


def _fallback_scored_source(src_files: ExamDerivedFiles, dest_files: ExamDerivedFiles) -> Path:
    return src_files.scored if src_files.scored.exists() else dest_files.unscored


def _apply_answer_key_scoring(src_files: ExamDerivedFiles, dest_files: ExamDerivedFiles, deps: ExamUploadConfirmDeps) -> None:
    if not (dest_files.unscored.exists() and dest_files.answers.exists() and dest_files.questions.exists()):
        deps.copy2(src_files.scored, dest_files.scored)
        return
    try:
        try:
            answers = deps.load_exam_answer_key_from_csv(dest_files.answers)
            deps.ensure_questions_max_score(dest_files.questions, answers.keys(), 1.0)
        except Exception:
            _log.warning("answer key CSV load/ensure_max_score failed", exc_info=True)
        deps.apply_answer_key_to_responses_csv(dest_files.unscored, dest_files.answers, dest_files.questions, dest_files.scored)
    except Exception:
        _log.debug("operation failed", exc_info=True)
        deps.copy2(_fallback_scored_source(src_files, dest_files), dest_files.scored)


def _prepare_derived_outputs(
    job_id: str,
    job_dir: Path,
    dest_derived_dir: Path,
    override: Dict[str, Any],
    questions_override: Optional[List[Dict[str, Any]]],
    deps: ExamUploadConfirmDeps,
) -> ExamDerivedFiles:
    src_files = _derived_files(job_dir / "derived")
    dest_files = _derived_files(dest_derived_dir)
    if not src_files.scored.exists():
        deps.write_exam_job(job_id, {"status": "failed", "error": "responses missing", "step": "failed"})
        raise ExamUploadConfirmError(400, "responses missing")
    _copy_derived_inputs(src_files, dest_files, deps)
    _apply_questions_override(dest_files.questions, questions_override, deps)
    _apply_answer_key_override(dest_files.answers, str(override.get("answer_key_text") or "").strip(), deps)
    _apply_answer_key_scoring(src_files, dest_files, deps)
    return dest_files


def _run_exam_analysis(exam_id: str, dest_derived_dir: Path, deps: ExamUploadConfirmDeps) -> tuple[Path, Path]:
    analysis_dir = _resolve_analysis_dir(deps.data_dir, exam_id)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    draft_json = analysis_dir / "draft.json"
    draft_md = analysis_dir / "draft.md"
    try:
        script = deps.app_root / "skills" / "physics-teacher-ops" / "scripts" / "compute_exam_metrics.py"
        deps.run_script(
            [
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
        )
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        deps.diag_log("exam_upload.analysis_failed", {"exam_id": exam_id, "error": str(exc)[:200]})
    return draft_json, draft_md


def _build_manifest(
    *,
    exam_id: str,
    meta: Dict[str, Any],
    counts: Any,
    dest_files: ExamDerivedFiles,
    draft_json: Path,
    draft_md: Path,
    deps: ExamUploadConfirmDeps,
) -> Dict[str, Any]:
    return {
        "exam_id": exam_id,
        "generated_at": deps.now_iso(),
        "meta": meta,
        "files": {
            "responses_scored": _to_rel(dest_files.scored, deps.app_root),
            "responses_unscored": _to_rel(dest_files.unscored, deps.app_root) if dest_files.unscored.exists() else "",
            "questions": _to_rel(dest_files.questions, deps.app_root),
            "answers": _to_rel(dest_files.answers, deps.app_root) if dest_files.answers.exists() else "",
            "analysis_draft_json": _to_rel(draft_json, deps.app_root) if draft_json.exists() else "",
            "analysis_draft_md": _to_rel(draft_md, deps.app_root) if draft_md.exists() else "",
        },
        "counts": counts or {},
    }


def confirm_exam_upload(
    job_id: str,
    job: Dict[str, Any],
    job_dir: Path,
    deps: ExamUploadConfirmDeps,
) -> Dict[str, Any]:
    deps.write_exam_job(job_id, {"status": "confirming", "step": "start", "progress": 5})

    parsed = _load_parsed_result(job_id, job_dir, deps)
    override = _as_dict(deps.load_exam_draft_override(job_dir))
    _require_confirmed_mapping(job_id, _merged_score_schema(parsed, override), deps)
    exam_id = _resolve_exam_id(parsed, job)
    meta = _merge_meta(parsed, override)
    questions_override = _questions_override(override)
    exam_dir, manifest_path = _prepare_exam_dir(job_id, exam_id, deps)

    deps.write_exam_job(job_id, {"step": "copy_files", "progress": 25})
    dest_derived_dir = _copy_upload_files(job, job_dir, exam_dir, deps)

    deps.write_exam_job(job_id, {"step": "write_derived", "progress": 50})
    dest_files = _prepare_derived_outputs(job_id, job_dir, dest_derived_dir, override, questions_override, deps)

    deps.write_exam_job(job_id, {"step": "analysis", "progress": 70})
    draft_json, draft_md = _run_exam_analysis(exam_id, dest_derived_dir, deps)

    deps.write_exam_job(job_id, {"step": "manifest", "progress": 90})
    manifest = _build_manifest(
        exam_id=exam_id,
        meta=meta,
        counts=parsed.get("counts"),
        dest_files=dest_files,
        draft_json=draft_json,
        draft_md=draft_md,
        deps=deps,
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    deps.write_exam_job(job_id, {"status": "confirmed", "step": "confirmed", "progress": 100, "exam_id": exam_id})
    return {"ok": True, "exam_id": exam_id, "status": "confirmed", "message": "考试已创建。"}
