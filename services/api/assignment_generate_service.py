from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .assignment_catalog_service import (
    coerce_assignment_kind,
    coerce_content_source,
)
from .assignment_generate_cli_service import (
    DRAFT_VISIBILITY_STATUS,
    append_assignment_generate_flag,
    append_assignment_generate_options,
    assignment_generate_script,
    generated_assignment_completion_policy,
    try_postprocess_assignment_meta,
)
from .auth_service import get_current_principal
from .paths import InvalidAssignmentDate
from .question_bank_select_service import ensure_questions_csv_header


class AssignmentGenerateError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class AssignmentGenerateDeps:
    app_root: Path
    optional_assignment_date: Callable[[Optional[str]], Optional[str]]
    ensure_requirements_for_assignment: Callable[..., Optional[Dict[str, Any]]]
    run_script: Callable[[list[str]], str]
    postprocess_assignment_meta: Callable[..., Any]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]


def _parse_requirements_json(requirements_json: Optional[str]) -> Optional[Dict[str, Any]]:
    if not requirements_json:
        return None
    try:
        return json.loads(requirements_json)
    except Exception:
        raise AssignmentGenerateError(400, "requirements_json is not valid JSON")


def _require_generate_owner(*, subject_id: Optional[str]) -> tuple[str, str]:
    teacher_id = str(getattr(get_current_principal(), "actor_id", "") or "").strip()
    subject_val = str(subject_id or "").strip()
    if not teacher_id:
        raise AssignmentGenerateError(400, "teacher_id_required")
    if not subject_val:
        raise AssignmentGenerateError(400, "subject_id_required")
    return teacher_id, subject_val


def _generate_assignment_date(date: Optional[str], deps: AssignmentGenerateDeps) -> str:
    try:
        return str(deps.optional_assignment_date(date) or "")
    except InvalidAssignmentDate as exc:
        raise AssignmentGenerateError(400, "invalid_assignment_date") from exc


def _ensure_assignment_requirements(
    *,
    assignment_id: str,
    date_str: str,
    requirements_payload: Optional[Dict[str, Any]],
    source: Optional[str],
    assignment_kind: str,
    deps: AssignmentGenerateDeps,
    skip_validation: bool,
) -> None:
    if skip_validation:
        return
    req_result = deps.ensure_requirements_for_assignment(
        assignment_id,
        date_str,
        requirements_payload,
        str(source or "teacher"),
        assignment_kind,
    )
    if req_result and req_result.get("error"):
        raise AssignmentGenerateError(400, req_result)


def _normalize_generate_axes(
    *,
    assignment_id: str,
    assignment_kind: Optional[str],
    content_source: Optional[str],
    deps: AssignmentGenerateDeps,
) -> tuple[str, str]:
    try:
        kind, defaulted = coerce_assignment_kind(assignment_kind)
    except ValueError as exc:
        raise AssignmentGenerateError(400, "invalid_assignment_kind") from exc
    if defaulted:
        deps.diag_log(
            "assignment.kind.defaulted",
            {"assignment_id": assignment_id, "assignment_kind": kind},
        )
    try:
        source = coerce_content_source(content_source, default="ai")
    except ValueError as exc:
        raise AssignmentGenerateError(400, "invalid_content_source") from exc
    if source != "ai":
        raise AssignmentGenerateError(400, "generate_requires_content_source_ai")
    return kind, source


def _run_problem_set_generate(
    *,
    assignment_id: str,
    kp: str,
    question_ids: Optional[str],
    per_kp: int,
    core_examples: Optional[str],
    generate_flag: bool,
    mode: Optional[str],
    date_str: str,
    due_at: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    source: Optional[str],
    teacher_id: str,
    subject_val: str,
    deps: AssignmentGenerateDeps,
) -> Dict[str, Any]:
    args = [
        "python3",
        str(assignment_generate_script(deps.app_root)),
        "--assignment-id",
        assignment_id,
        "--per-kp",
        str(per_kp),
    ]
    append_assignment_generate_options(
        args,
        (
            ("--kp", kp),
            ("--question-ids", question_ids),
            ("--mode", mode),
            ("--date", date_str),
            ("--class-name", class_name),
            ("--student-ids", student_ids),
            ("--source", source),
            ("--core-examples", core_examples),
            ("--teacher-id", teacher_id),
            ("--subject-id", subject_val),
            ("--due-at", due_at),
            ("--visibility-status", DRAFT_VISIBILITY_STATUS),
        ),
    )
    append_assignment_generate_flag(args, flag="--generate", enabled=generate_flag)
    try:
        out = deps.run_script(args)
    except Exception as exc:
        detail = str(getattr(exc, "detail", "") or exc)
        if "question_bank_insufficient" in detail:
            raise AssignmentGenerateError(409, "question_bank_insufficient") from exc
        raise
    try_postprocess_assignment_meta(
        assignment_id=assignment_id,
        due_at=due_at,
        postprocess_assignment_meta=deps.postprocess_assignment_meta,
        diag_log=deps.diag_log,
        visibility_status=DRAFT_VISIBILITY_STATUS,
        teacher_id=teacher_id,
        subject_id=subject_val,
        completion_policy=generated_assignment_completion_policy(
            assignment_kind="problem_set"
        ),
        content_source="ai",
        assignment_kind="problem_set",
    )
    return {"ok": True, "output": out, "draft": _load_generate_draft(assignment_id, deps)}


def _load_generate_draft(assignment_id: str, deps: AssignmentGenerateDeps) -> Dict[str, Any]:
    from .paths import DATA_DIR

    out_dir = Path(DATA_DIR) / "assignments" / assignment_id
    req_path = out_dir / "requirements.json"
    try:
        requirements = json.loads(req_path.read_text(encoding="utf-8")) if req_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        requirements = {}
    if not isinstance(requirements, dict):
        requirements = {}
    return {
        "assignment_id": assignment_id,
        "requirements": requirements,
        "questions": [],
        "requirements_missing": [],
        "assignment_kind": "problem_set",
        "content_source": "ai",
    }


def _parse_brief_llm_json(text: str) -> Optional[Dict[str, Any]]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _draft_non_problem_set(
    *,
    assignment_id: str,
    assignment_kind: str,
    teacher_id: str,
    subject_val: str,
    date_str: str,
    due_at: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    requirements_payload: Optional[Dict[str, Any]],
    seed: Optional[str],
    deps: AssignmentGenerateDeps,
) -> Dict[str, Any]:
    from .paths import DATA_DIR

    req = dict(requirements_payload or {})
    topic = str(req.get("topic") or "").strip()
    subject = str(req.get("subject") or "").strip() or subject_val
    grade_level = str(req.get("grade_level") or "").strip()
    if not topic or not grade_level:
        raise AssignmentGenerateError(400, "generate_failed")
    prompt_path = (
        deps.app_root / "prompts" / "v1" / "teacher" / "skills" / "assignment_brief_draft.md"
    )
    try:
        system = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssignmentGenerateError(400, "generate_failed") from exc
    user = json.dumps(
        {
            "assignment_kind": assignment_kind,
            "subject": subject,
            "topic": topic,
            "grade_level": grade_level,
            "seed": str(seed or "").strip(),
        },
        ensure_ascii=False,
    )
    try:
        from llm_gateway import LLMGateway, UnifiedLLMRequest

        result = LLMGateway().generate(
            UnifiedLLMRequest(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            ),
            allow_fallback=True,
        )
        parsed = _parse_brief_llm_json(getattr(result, "text", "") or "")
    except Exception as exc:
        raise AssignmentGenerateError(400, "generate_failed") from exc
    brief = str((parsed or {}).get("brief") or "").strip()
    if not brief:
        raise AssignmentGenerateError(400, "generate_failed")
    goals = (parsed or {}).get("discussion_goals") or []
    if not isinstance(goals, list):
        goals = []
    goals = [str(item).strip() for item in goals if str(item).strip()][:5]
    rubric = str((parsed or {}).get("rubric") or "").strip()
    out_dir = Path(DATA_DIR) / "assignments" / assignment_id
    out_dir.mkdir(parents=True, exist_ok=True)
    requirements = {
        "subject": subject,
        "topic": topic,
        "grade_level": grade_level,
        "brief": brief,
        "discussion_goals": goals,
    }
    (out_dir / "requirements.json").write_text(
        json.dumps({"assignment_id": assignment_id, **requirements}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "brief.md").write_text(brief + "\n", encoding="utf-8")
    if rubric:
        (out_dir / "rubric.md").write_text(rubric + "\n", encoding="utf-8")
    ensure_questions_csv_header(out_dir / "questions.csv")
    from .core_utils import parse_ids_value, resolve_scope

    student_ids_list = parse_ids_value(student_ids)
    scope_val = resolve_scope("", student_ids_list, str(class_name or ""))
    meta = {
        "assignment_id": assignment_id,
        "teacher_id": teacher_id,
        "subject_id": subject_val,
        "pack_id": subject_val,
        "date": date_str,
        "due_at": due_at or "",
        "visibility_status": DRAFT_VISIBILITY_STATUS,
        "archived_at": None,
        "mode": "auto",
        "content_source": "ai",
        "assignment_kind": assignment_kind,
        "target_kp": [],
        "question_ids": [],
        "class_name": class_name or "",
        "student_ids": student_ids_list,
        "scope": scope_val,
        "source": "teacher",
        "completion_policy": generated_assignment_completion_policy(
            assignment_kind=assignment_kind
        ),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try_postprocess_assignment_meta(
        assignment_id=assignment_id,
        due_at=due_at,
        postprocess_assignment_meta=deps.postprocess_assignment_meta,
        diag_log=deps.diag_log,
        visibility_status=DRAFT_VISIBILITY_STATUS,
        teacher_id=teacher_id,
        subject_id=subject_val,
        completion_policy=generated_assignment_completion_policy(
            assignment_kind=assignment_kind
        ),
        content_source="ai",
        assignment_kind=assignment_kind,
    )
    deps.diag_log(
        "assignment.draft.generate",
        {"assignment_id": assignment_id, "kind": assignment_kind, "source": "ai", "ok": True},
    )
    return {
        "ok": True,
        "output": "brief_draft",
        "draft": {
            "assignment_id": assignment_id,
            "requirements": requirements,
            "questions": [],
            "requirements_missing": [],
            "assignment_kind": assignment_kind,
            "content_source": "ai",
        },
    }


def generate_assignment(
    *,
    assignment_id: str,
    kp: str,
    question_ids: Optional[str],
    per_kp: int,
    core_examples: Optional[str],
    generate: bool,
    mode: Optional[str],
    date: Optional[str],
    due_at: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    source: Optional[str],
    requirements_json: Optional[str],
    subject_id: Optional[str] = None,
    assignment_kind: Optional[str] = None,
    content_source: Optional[str] = None,
    seed: Optional[str] = None,
    skip_validation: bool = False,
    deps: AssignmentGenerateDeps,
) -> Dict[str, Any]:
    requirements_payload = _parse_requirements_json(requirements_json)
    date_str = _generate_assignment_date(date, deps)
    kind, source_axis = _normalize_generate_axes(
        assignment_id=assignment_id,
        assignment_kind=assignment_kind,
        content_source=content_source,
        deps=deps,
    )
    generate_flag = bool(generate)
    if kind != "problem_set":
        generate_flag = False
    _ensure_assignment_requirements(
        assignment_id=assignment_id,
        date_str=date_str,
        requirements_payload=requirements_payload,
        source=source,
        assignment_kind=kind,
        deps=deps,
        skip_validation=skip_validation or kind != "problem_set",
    )
    teacher_id, subject_val = _require_generate_owner(subject_id=subject_id)
    if kind != "problem_set":
        return _draft_non_problem_set(
            assignment_id=assignment_id,
            assignment_kind=kind,
            teacher_id=teacher_id,
            subject_val=subject_val,
            date_str=date_str,
            due_at=due_at,
            class_name=class_name,
            student_ids=student_ids,
            requirements_payload=requirements_payload,
            seed=seed,
            deps=deps,
        )
    del source_axis
    return _run_problem_set_generate(
        assignment_id=assignment_id,
        kp=kp,
        question_ids=question_ids,
        per_kp=per_kp,
        core_examples=core_examples,
        generate_flag=generate_flag,
        mode=mode,
        date_str=date_str,
        due_at=due_at,
        class_name=class_name,
        student_ids=student_ids,
        source=source,
        teacher_id=teacher_id,
        subject_val=subject_val,
        deps=deps,
    )
