from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


def exam_upload_not_ready_detail(job: Dict[str, Any], message: str) -> Dict[str, Any]:
    return {
        "error": "job_not_ready",
        "message": message,
        "status": job.get("status"),
        "step": job.get("step"),
        "progress": job.get("progress"),
    }


def load_exam_draft_override(job_dir: Path) -> Dict[str, Any]:
    override_path = job_dir / "draft_override.json"
    if not override_path.exists():
        return {}
    try:
        data = json.loads(override_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_exam_draft_override(
    job_dir: Path,
    current_override: Dict[str, Any],
    *,
    meta: Any = None,
    questions: Any = None,
    score_schema: Any = None,
    answer_key_text: Any = None,
) -> Dict[str, Any]:
    override = dict(current_override or {})
    if meta is not None:
        override["meta"] = meta
    if questions is not None:
        override["questions"] = questions
    if score_schema is not None:
        override["score_schema"] = score_schema
    if answer_key_text is not None:
        override["answer_key_text"] = str(answer_key_text or "")
    override_path = job_dir / "draft_override.json"
    override_path.write_text(json.dumps(override, ensure_ascii=False, indent=2), encoding="utf-8")
    return override


def build_exam_upload_draft(
    job_id: str,
    job: Dict[str, Any],
    parsed: Dict[str, Any],
    override: Dict[str, Any],
    *,
    parse_exam_answer_key_text: Callable[[str], Tuple[List[Dict[str, Any]], List[str]]],
    answer_text_excerpt: str,
) -> Dict[str, Any]:
    meta = parsed.get("meta") or {}
    questions = parsed.get("questions") or []
    score_schema = parsed.get("score_schema") or {}
    warnings = parsed.get("warnings") or []
    score_schema = parsed.get("score_schema") or {}
    needs_confirm = bool(parsed.get("needs_confirm"))
    answer_key = parsed.get("answer_key") or {}
    scoring = parsed.get("scoring") or {}
    counts_scored = parsed.get("counts_scored") or {}

    if isinstance(override.get("meta"), dict) and override.get("meta"):
        meta = {**meta, **override.get("meta")}
    if isinstance(override.get("questions"), list) and override.get("questions"):
        questions = override.get("questions")
    if isinstance(override.get("score_schema"), dict) and override.get("score_schema"):
        score_schema = {**score_schema, **override.get("score_schema")}
    selected_candidate_id = str(
        (
            ((score_schema.get("subject") or {}).get("selected_candidate_id")
            if isinstance(score_schema.get("subject"), dict)
            else score_schema.get("selected_candidate_id"))
        )
        or ""
    ).strip()
    if score_schema.get("confirm") is True or selected_candidate_id:
        needs_confirm = False

    answer_key_text = str(override.get("answer_key_text") or "").strip()
    if answer_key_text:
        override_answers, override_ans_warnings = parse_exam_answer_key_text(answer_key_text)
        answer_key = {
            "count": len(override_answers),
            "source": "override",
            "warnings": override_ans_warnings,
        }
    elif isinstance(answer_key, dict) and answer_key:
        answer_key = {**answer_key, "source": "ocr" if answer_key.get("count") else "none"}

    return {
        "job_id": job_id,
        "exam_id": parsed.get("exam_id") or job.get("exam_id"),
        "date": meta.get("date") or job.get("date"),
        "class_name": meta.get("class_name") or job.get("class_name"),
        "paper_files": parsed.get("paper_files") or job.get("paper_files") or [],
        "score_files": parsed.get("score_files") or job.get("score_files") or [],
        "answer_files": parsed.get("answer_files") or job.get("answer_files") or [],
        "counts": parsed.get("counts") or {},
        "counts_scored": counts_scored,
        "totals_summary": parsed.get("totals_summary") or {},
        "scoring": scoring,
        "meta": meta,
        "questions": questions,
        "score_schema": score_schema,
        "answer_key": answer_key,
        "answer_key_text": answer_key_text,
        "answer_text_excerpt": answer_text_excerpt,
        "warnings": warnings,
        "needs_confirm": needs_confirm,
        "draft_saved": bool(override),
        "draft_version": int(job.get("draft_version") or 1),
    }
