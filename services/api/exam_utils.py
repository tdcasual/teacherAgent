"""Exam utility functions extracted from app_core.py.

Pure functions for exam data parsing, path resolution, and chart normalization.
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import resolve_analysis_dir, resolve_exam_dir, resolve_manifest_path

__all__ = [
    "parse_score_value",
    "read_questions_csv",
    "compute_exam_totals",
    "_parse_question_no_int",
    "_median_float",
    "_normalize_question_no_list",
    "_EXAM_CHART_DEFAULT_TYPES",
    "_EXAM_CHART_TYPE_ALIASES",
    "_normalize_exam_chart_types",
    "_safe_int_arg",
    "load_exam_manifest",
    "exam_responses_path",
    "exam_questions_path",
    "exam_analysis_draft_path",
    "_parse_xlsx_with_script",
]


def parse_score_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def read_questions_csv(path: Path) -> Dict[str, Dict[str, Any]]:
    questions: Dict[str, Dict[str, Any]] = {}
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = str(row.get("question_id") or "").strip()
                if not qid:
                    continue
                max_score = parse_score_value(row.get("max_score"))
                questions[qid] = {
                    "question_id": qid,
                    "question_no": str(row.get("question_no") or "").strip(),
                    "sub_no": str(row.get("sub_no") or "").strip(),
                    "order": str(row.get("order") or "").strip(),
                    "max_score": max_score,
                }
    except Exception:
        return questions
    return questions


def compute_exam_totals(responses_path: Path) -> Dict[str, Any]:
    totals: Dict[str, float] = {}
    student_meta: Dict[str, Dict[str, str]] = {}
    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            score = parse_score_value(row.get("score"))
            if score is None:
                continue
            student_id = str(row.get("student_id") or row.get("student_name") or "").strip()
            if not student_id:
                continue
            totals[student_id] = totals.get(student_id, 0.0) + score
            if student_id not in student_meta:
                student_meta[student_id] = {
                    "student_id": student_id,
                    "student_name": str(row.get("student_name") or "").strip(),
                    "class_name": str(row.get("class_name") or "").strip(),
                }
    return {"totals": totals, "students": student_meta}


def _load_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_exam_manifest(exam_id: str) -> Dict[str, Any]:
    exam_id = str(exam_id or "").strip()
    if not exam_id:
        return {}
    try:
        manifest_path = resolve_exam_dir(exam_id) / "manifest.json"
    except ValueError:
        return {}
    return _load_json_file(manifest_path)


def exam_responses_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    for key in ("responses_scored", "responses", "responses_csv"):
        path = resolve_manifest_path(files.get(key))
        if path and path.exists():
            return path
    return None


def exam_questions_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    for key in ("questions", "questions_csv"):
        path = resolve_manifest_path(files.get(key))
        if path and path.exists():
            return path
    return None


def exam_analysis_draft_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if isinstance(files, dict):
        path = resolve_manifest_path(files.get("analysis_draft_json"))
        if path and path.exists():
            return path
    exam_id = str(manifest.get("exam_id") or "").strip()
    if not exam_id:
        return None
    try:
        fallback = resolve_analysis_dir(exam_id) / "draft.json"
    except ValueError:
        return None
    return fallback if fallback.exists() else None


def _parse_question_no_int(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        out = int(text)
        return out if out > 0 else None
    except Exception:
        pass
    match = re.match(r"^(\d+)", text)
    if not match:
        return None
    try:
        out = int(match.group(1))
    except Exception:
        return None
    return out if out > 0 else None


def _median_float(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    size = len(ordered)
    mid = size // 2
    if size % 2 == 1:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _normalize_question_no_list(value: Any, maximum: int = 200) -> List[int]:
    raw_items: List[Any] = []
    if isinstance(value, list):
        raw_items = list(value)
    elif value is not None:
        raw_items = [x for x in re.split(r"[,\s，;；]+", str(value)) if x]
    normalized: List[int] = []
    seen: set[int] = set()
    for item in raw_items:
        q_no = _parse_question_no_int(item)
        if q_no is None or q_no in seen:
            continue
        seen.add(q_no)
        normalized.append(q_no)
        if len(normalized) >= maximum:
            break
    return normalized


_EXAM_CHART_DEFAULT_TYPES = ["score_distribution", "knowledge_radar", "class_compare", "question_discrimination"]
_EXAM_CHART_TYPE_ALIASES = {
    "score_distribution": "score_distribution",
    "distribution": "score_distribution",
    "histogram": "score_distribution",
    "成绩分布": "score_distribution",
    "分布": "score_distribution",
    "knowledge_radar": "knowledge_radar",
    "radar": "knowledge_radar",
    "knowledge": "knowledge_radar",
    "知识点雷达": "knowledge_radar",
    "雷达图": "knowledge_radar",
    "class_compare": "class_compare",
    "class": "class_compare",
    "group_compare": "class_compare",
    "班级对比": "class_compare",
    "对比": "class_compare",
    "question_discrimination": "question_discrimination",
    "discrimination": "question_discrimination",
    "区分度": "question_discrimination",
    "题目区分度": "question_discrimination",
}


def _safe_int_arg(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        out = int(value)
    except Exception:
        out = default
    if out < minimum:
        return minimum
    if out > maximum:
        return maximum
    return out


def _normalize_exam_chart_types(value: Any) -> List[str]:
    raw_items: List[str] = []
    if isinstance(value, list):
        raw_items = [str(v or "").strip() for v in value]
    elif isinstance(value, str):
        raw_items = [x.strip() for x in re.split(r"[,\s，;；]+", value) if x.strip()]
    normalized: List[str] = []
    for item in raw_items:
        key = _EXAM_CHART_TYPE_ALIASES.get(item.lower()) or _EXAM_CHART_TYPE_ALIASES.get(item)
        if not key:
            continue
        if key not in normalized:
            normalized.append(key)
    return normalized or list(_EXAM_CHART_DEFAULT_TYPES)


def _parse_xlsx_with_script(
    xlsx_path: Path,
    out_csv: Path,
    exam_id: str,
    class_name_hint: str,
) -> Optional[List[Dict[str, Any]]]:
    from .config import APP_ROOT
    script = APP_ROOT / "skills" / "physics-teacher-ops" / "scripts" / "parse_scores.py"
    cmd = ["python3", str(script), "--scores", str(xlsx_path), "--exam-id", exam_id, "--out", str(out_csv)]
    if class_name_hint:
        cmd += ["--class-name", class_name_hint]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), cwd=str(APP_ROOT))
    if proc.returncode != 0 or not out_csv.exists():
        return None
    file_rows: List[Dict[str, Any]] = []
    with out_csv.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            item = dict(row)
            item["score"] = parse_score_value(row.get("score"))
            item["is_correct"] = row.get("is_correct") or ""
            file_rows.append(item)
    return file_rows