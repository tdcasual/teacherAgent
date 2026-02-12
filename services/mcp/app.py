from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from services.common.tool_registry import DEFAULT_TOOL_REGISTRY
import logging
_log = logging.getLogger(__name__)


APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", APP_ROOT / "data"))
API_KEY = os.getenv("MCP_API_KEY", "")
SCRIPT_TIMEOUT_ENV = os.getenv("MCP_SCRIPT_TIMEOUT_SEC", "600").strip()
SCRIPT_TIMEOUT_SEC: Optional[float]
if not SCRIPT_TIMEOUT_ENV or SCRIPT_TIMEOUT_ENV.lower() in {"0", "none", "null", "inf", "infinite"}:
    SCRIPT_TIMEOUT_SEC = None
else:
    try:
        SCRIPT_TIMEOUT_SEC = float(SCRIPT_TIMEOUT_ENV)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        SCRIPT_TIMEOUT_SEC = 600.0

app = FastAPI(title="Physics MCP Server", version="0.2.0")

_SAFE_ID_RE = re.compile(r"^[^\x00/\\\\]+$")


class JsonRpcRequest(BaseModel):
    jsonrpc: str
    id: Optional[Union[str, int]]
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)

MCP_TOOL_NAMES = [
    "student.search",
    "student.profile.get",
    "student.profile.update",
    "exam.list",
    "exam.get",
    "exam.analysis.get",
    "exam.students.list",
    "exam.student.get",
    "exam.question.get",
    "assignment.list",
    "assignment.generate",
    "assignment.render",
    "lesson.list",
    "lesson.capture",
    "core_example.search",
    "core_example.register",
    "core_example.render",
]

TOOLS = [DEFAULT_TOOL_REGISTRY.require(name).to_mcp() for name in MCP_TOOL_NAMES]


@app.get("/health")
async def health():
    return {"status": "ok"}


def auth(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

def _jsonrpc_ok(request_id: Optional[Union[str, int]], result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(
    request_id: Optional[Union[str, int]],
    code: int,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": int(code), "message": str(message)}
    if data:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": err}


def _require_safe_id(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"missing required field: {field}")
    if not _SAFE_ID_RE.match(text):
        raise ValueError(f"invalid id for {field}")
    return text


def _resolve_manifest_path(path_value: Any) -> Optional[Path]:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (APP_ROOT / path).resolve()
    return path


def _load_exam_manifest(exam_id: str) -> Dict[str, Any]:
    manifest_path = DATA_DIR / "exams" / exam_id / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        _log.debug("JSON parse failed", exc_info=True)
        return {}


def _exam_responses_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    for key in ("responses_scored", "responses", "responses_csv"):
        path = _resolve_manifest_path(files.get(key))
        if path and path.exists():
            return path
    return None


def _exam_questions_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return None
    for key in ("questions", "questions_csv"):
        path = _resolve_manifest_path(files.get(key))
        if path and path.exists():
            return path
    return None


def _exam_analysis_draft_path(manifest: Dict[str, Any]) -> Optional[Path]:
    files = manifest.get("files") or {}
    if isinstance(files, dict):
        path = _resolve_manifest_path(files.get("analysis_draft_json"))
        if path and path.exists():
            return path
    exam_id = str(manifest.get("exam_id") or "").strip()
    if not exam_id:
        return None
    fallback = DATA_DIR / "analysis" / exam_id / "draft.json"
    return fallback if fallback.exists() else None


def _parse_score_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        match = re.search(r"-?\\d+(\\.\\d+)?", text)
        if not match:
            return None
        try:
            return float(match.group(0))
        except Exception:
            _log.debug("numeric conversion failed", exc_info=True)
            return None


def _read_questions_csv(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if not path or not path.exists():
        return {}
    questions: Dict[str, Dict[str, Any]] = {}
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = str(row.get("question_id") or "").strip()
                if not qid:
                    continue
                questions[qid] = {
                    "question_id": qid,
                    "question_no": str(row.get("question_no") or "").strip(),
                    "sub_no": str(row.get("sub_no") or "").strip(),
                    "order": str(row.get("order") or "").strip(),
                    "max_score": _parse_score_value(row.get("max_score")),
                }
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return {}
    return questions


def _compute_exam_totals(responses_path: Path) -> Dict[str, Any]:
    totals: Dict[str, float] = {}
    student_meta: Dict[str, Dict[str, str]] = {}
    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            score = _parse_score_value(row.get("score"))
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


def _tool_exam_list() -> Dict[str, Any]:
    exams_dir = DATA_DIR / "exams"
    if not exams_dir.exists():
        return {"ok": True, "exams": []}
    items: List[Dict[str, Any]] = []
    for folder in exams_dir.iterdir():
        if not folder.is_dir():
            continue
        manifest_path = folder / "manifest.json"
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        except Exception:
            _log.debug("JSON parse failed", exc_info=True)
            data = {}
        exam_id = data.get("exam_id") or folder.name
        generated_at = data.get("generated_at")
        counts = data.get("counts", {}) if isinstance(data.get("counts"), dict) else {}
        items.append(
            {
                "exam_id": exam_id,
                "generated_at": generated_at,
                "students": counts.get("students"),
                "responses": counts.get("responses"),
            }
        )
    items.sort(key=lambda x: x.get("generated_at") or "", reverse=True)
    return {"ok": True, "exams": items}


def _tool_exam_get(args: Dict[str, Any]) -> Dict[str, Any]:
    exam_id = _require_safe_id(args.get("exam_id"), "exam_id")
    manifest = _load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    responses_path = _exam_responses_path(manifest)
    questions_path = _exam_questions_path(manifest)
    analysis_path = _exam_analysis_draft_path(manifest)
    questions = _read_questions_csv(questions_path)
    totals_result = _compute_exam_totals(responses_path) if responses_path and responses_path.exists() else {"totals": {}, "students": {}}
    totals = totals_result["totals"]
    total_values = sorted(totals.values())
    avg_total = sum(total_values) / len(total_values) if total_values else 0.0
    median_total = total_values[len(total_values) // 2] if total_values else 0.0
    meta = manifest.get("meta") if isinstance(manifest.get("meta"), dict) else {}
    score_mode = meta.get("score_mode") if isinstance(meta, dict) else None
    if not score_mode:
        score_mode = "question" if questions else "unknown"
    return {
        "ok": True,
        "exam_id": manifest.get("exam_id") or exam_id,
        "generated_at": manifest.get("generated_at"),
        "meta": meta or {},
        "counts": {"students": len(totals), "questions": len(questions)},
        "totals_summary": {
            "avg_total": round(avg_total, 3),
            "median_total": round(median_total, 3),
            "max_total_observed": max(total_values) if total_values else 0.0,
            "min_total_observed": min(total_values) if total_values else 0.0,
        },
        "score_mode": score_mode,
        "files": {
            "manifest": str((DATA_DIR / "exams" / exam_id / "manifest.json").resolve()),
            "responses": str(responses_path) if responses_path else None,
            "questions": str(questions_path) if questions_path else None,
            "analysis_draft": str(analysis_path) if analysis_path else None,
        },
    }


def _tool_exam_analysis_get(args: Dict[str, Any]) -> Dict[str, Any]:
    exam_id = _require_safe_id(args.get("exam_id"), "exam_id")
    manifest = _load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    analysis_path = _exam_analysis_draft_path(manifest)
    if analysis_path and analysis_path.exists():
        try:
            payload = json.loads(analysis_path.read_text(encoding="utf-8"))
            return {"ok": True, "exam_id": exam_id, "analysis": payload, "source": str(analysis_path)}
        except Exception:
            _log.debug("JSON parse failed", exc_info=True)
            return {"error": "analysis_parse_failed", "exam_id": exam_id, "source": str(analysis_path)}
    responses_path = _exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}
    totals_result = _compute_exam_totals(responses_path)
    totals = sorted(totals_result["totals"].values())
    avg_total = sum(totals) / len(totals) if totals else 0.0
    median_total = totals[len(totals) // 2] if totals else 0.0
    return {
        "ok": True,
        "exam_id": exam_id,
        "analysis": {
            "exam_id": exam_id,
            "generated_at": None,
            "totals": {
                "student_count": len(totals),
                "avg_total": round(avg_total, 3),
                "median_total": round(median_total, 3),
                "max_total_observed": max(totals) if totals else 0.0,
                "min_total_observed": min(totals) if totals else 0.0,
            },
            "notes": "No precomputed analysis draft found; returned minimal totals summary.",
        },
        "source": "computed",
    }


def _tool_exam_students_list(args: Dict[str, Any]) -> Dict[str, Any]:
    exam_id = _require_safe_id(args.get("exam_id"), "exam_id")
    limit = int(args.get("limit", 50) or 50)
    manifest = _load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    responses_path = _exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}
    totals_result = _compute_exam_totals(responses_path)
    totals: Dict[str, float] = totals_result["totals"]
    students_meta: Dict[str, Dict[str, str]] = totals_result["students"]
    items = []
    for student_id, total_score in totals.items():
        meta = students_meta.get(student_id) or {}
        items.append(
            {
                "student_id": student_id,
                "student_name": meta.get("student_name", ""),
                "class_name": meta.get("class_name", ""),
                "total_score": round(total_score, 3),
            }
        )
    items.sort(key=lambda x: x["total_score"], reverse=True)
    total_students = len(items)
    for idx, item in enumerate(items, start=1):
        item["rank"] = idx
        item["percentile"] = round(1.0 - (idx - 1) / total_students, 4) if total_students else 0.0
    take = max(1, min(limit, 500))
    return {"ok": True, "exam_id": exam_id, "total_students": total_students, "students": items[:take]}


def _tool_exam_student_get(args: Dict[str, Any]) -> Dict[str, Any]:
    exam_id = _require_safe_id(args.get("exam_id"), "exam_id")
    student_id = str(args.get("student_id") or "").strip() or None
    student_name = str(args.get("student_name") or "").strip() or None
    class_name = str(args.get("class_name") or "").strip() or None
    if student_id and not _SAFE_ID_RE.match(student_id):
        return {"error": "invalid_student_id"}
    manifest = _load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    responses_path = _exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}
    questions = _read_questions_csv(_exam_questions_path(manifest))

    if not student_id and student_name:
        candidates = []
        with responses_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if class_name and str(row.get("class_name") or "").strip() != class_name:
                    continue
                if str(row.get("student_name") or "").strip() != student_name:
                    continue
                sid = str(row.get("student_id") or "").strip()
                if sid:
                    candidates.append(sid)
        candidates = sorted(set(candidates))
        if not candidates:
            return {"error": "student_not_found", "exam_id": exam_id}
        if len(candidates) > 1:
            return {"error": "multiple_students", "exam_id": exam_id, "candidates": candidates[:10]}
        student_id = candidates[0]

    if not student_id:
        return {"error": "student_not_specified", "exam_id": exam_id, "message": "请提供 student_id 或 student_name。"}

    total_score = 0.0
    per_question: Dict[str, Dict[str, Any]] = {}
    student_meta: Dict[str, str] = {"student_id": student_id, "student_name": "", "class_name": ""}
    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = str(row.get("student_id") or row.get("student_name") or "").strip()
            if sid != student_id:
                continue
            student_meta["student_name"] = str(row.get("student_name") or student_meta["student_name"]).strip()
            student_meta["class_name"] = str(row.get("class_name") or student_meta["class_name"]).strip()
            qid = str(row.get("question_id") or "").strip()
            if not qid:
                continue
            score = _parse_score_value(row.get("score"))
            if score is not None:
                total_score += score
            per_question[qid] = {
                "question_id": qid,
                "question_no": str(row.get("question_no") or questions.get(qid, {}).get("question_no") or "").strip(),
                "sub_no": str(row.get("sub_no") or "").strip(),
                "score": score,
                "max_score": questions.get(qid, {}).get("max_score"),
                "is_correct": row.get("is_correct"),
                "raw_value": row.get("raw_value"),
                "raw_answer": row.get("raw_answer"),
            }

    question_scores = list(per_question.values())
    question_scores.sort(key=lambda x: int(x.get("question_no") or "0") if str(x.get("question_no") or "").isdigit() else 9999)
    return {
        "ok": True,
        "exam_id": exam_id,
        "student": {**student_meta, "total_score": round(total_score, 3)},
        "question_scores": question_scores,
        "question_count": len(question_scores),
    }


def _tool_exam_question_get(args: Dict[str, Any]) -> Dict[str, Any]:
    exam_id = _require_safe_id(args.get("exam_id"), "exam_id")
    question_id = str(args.get("question_id") or "").strip() or None
    question_no = str(args.get("question_no") or "").strip() or None
    manifest = _load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    responses_path = _exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}
    questions = _read_questions_csv(_exam_questions_path(manifest))
    if not question_id and question_no:
        for qid, q in questions.items():
            if str(q.get("question_no") or "").strip() == question_no:
                question_id = qid
                break
    if not question_id:
        return {"error": "question_not_specified", "exam_id": exam_id, "message": "请提供 question_id 或 question_no。"}

    scores: List[float] = []
    correct_flags: List[int] = []
    by_student: List[Dict[str, Any]] = []
    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = str(row.get("question_id") or "").strip()
            if qid != question_id:
                continue
            score = _parse_score_value(row.get("score"))
            if score is not None:
                scores.append(score)
            is_correct = row.get("is_correct")
            if is_correct not in (None, ""):
                try:
                    correct_flags.append(int(is_correct))
                except Exception:
                    _log.debug("numeric conversion failed", exc_info=True)
                    pass
            by_student.append(
                {
                    "student_id": str(row.get("student_id") or row.get("student_name") or "").strip(),
                    "student_name": str(row.get("student_name") or "").strip(),
                    "class_name": str(row.get("class_name") or "").strip(),
                    "score": score,
                    "raw_value": row.get("raw_value"),
                }
            )

    avg_score = sum(scores) / len(scores) if scores else 0.0
    max_score = questions.get(question_id, {}).get("max_score")
    loss_rate = (max_score - avg_score) / max_score if max_score else None
    correct_rate = sum(correct_flags) / len(correct_flags) if correct_flags else None

    dist: Dict[str, int] = {}
    for s in scores:
        key = str(int(s)) if float(s).is_integer() else str(s)
        dist[key] = dist.get(key, 0) + 1

    by_student_sorted = sorted(by_student, key=lambda x: (x["score"] is None, -(x["score"] or 0)))
    top_students = [x for x in by_student_sorted if x.get("student_id")][:5]
    bottom_students = sorted(by_student, key=lambda x: (x["score"] is None, x["score"] or 0))[:5]

    return {
        "ok": True,
        "exam_id": exam_id,
        "question": {"question_id": question_id, "question_no": questions.get(question_id, {}).get("question_no"), "max_score": max_score},
        "stats": {
            "count": len(scores),
            "avg_score": round(avg_score, 3),
            "loss_rate": round(loss_rate, 4) if isinstance(loss_rate, float) else loss_rate,
            "correct_rate": round(correct_rate, 4) if isinstance(correct_rate, float) else correct_rate,
        },
        "distribution": dist,
        "top_students": top_students,
        "bottom_students": bottom_students,
    }


def _tool_assignment_list() -> Dict[str, Any]:
    base = DATA_DIR / "assignments"
    if not base.exists():
        return {"ok": True, "assignments": []}
    items = []
    for folder in base.iterdir():
        if folder.is_dir():
            items.append(folder.name)
    items.sort(reverse=True)
    return {"ok": True, "assignments": items}


def _tool_lesson_list() -> Dict[str, Any]:
    base = DATA_DIR / "lessons"
    if not base.exists():
        return {"ok": True, "lessons": []}
    items = []
    for folder in base.iterdir():
        if folder.is_dir():
            items.append(folder.name)
    items.sort(reverse=True)
    return {"ok": True, "lessons": items}


def _tool_student_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = str(args.get("query") or "").strip()
    limit = max(1, min(int(args.get("limit", 5) or 5), 50))
    if not query:
        return {"error": "missing_query"}
    base = DATA_DIR / "student_profiles"
    if not base.exists():
        return {"ok": True, "query": query, "students": []}
    results = []
    q = query.lower()
    for path in base.glob("*.json"):
        sid = path.stem
        if q in sid.lower():
            try:
                profile = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                _log.debug("JSON parse failed", exc_info=True)
                profile = {}
            results.append(
                {
                    "student_id": sid,
                    "student_name": str(profile.get("student_name") or "").strip(),
                    "class_name": str(profile.get("class_name") or "").strip(),
                }
            )
            if len(results) >= limit:
                break
    return {"ok": True, "query": query, "students": results[:limit]}

def run_script(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, cwd=str(APP_ROOT), timeout=SCRIPT_TIMEOUT_SEC)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr or proc.stdout)
    return proc.stdout


@app.post("/mcp")
async def mcp_rpc(req: JsonRpcRequest, x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)

    if req.method == "tools/list":
        return _jsonrpc_ok(req.id, TOOLS)

    if req.method == "initialize":
        return _jsonrpc_ok(
            req.id,
            {
                "serverInfo": {"name": app.title, "version": app.version},
                "capabilities": {"tools": {"listChanged": False}},
            },
        )

    if req.method == "tools/call":
        name = req.params.get("name")
        args = req.params.get("arguments", {})
        if not isinstance(name, str) or not name.strip():
            return _jsonrpc_error(req.id, -32602, "missing required field: name")
        name = name.strip()
        if name not in MCP_TOOL_NAMES:
            return _jsonrpc_error(req.id, -32601, f"Unknown tool: {name}")
        if not isinstance(args, dict):
            args = {}
        issues = DEFAULT_TOOL_REGISTRY.validate_arguments(name, args)
        if issues:
            return _jsonrpc_error(req.id, -32602, "invalid arguments", {"tool": name, "issues": issues[:20]})
        try:
            if name == "student.search":
                return _jsonrpc_ok(req.id, _tool_student_search(args))

            if name == "student.profile.get":
                student_id = _require_safe_id(args.get("student_id"), "student_id")
                profile_path = DATA_DIR / "student_profiles" / f"{student_id}.json"
                if not profile_path.exists():
                    return _jsonrpc_error(req.id, 404, "profile not found", {"student_id": student_id})
                return _jsonrpc_ok(req.id, json.loads(profile_path.read_text(encoding="utf-8")))

            if name == "student.profile.update":
                student_id = _require_safe_id(args.get("student_id"), "student_id")
                script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
                cmd = ["python3", str(script), "--student-id", student_id]
                for key in ("weak_kp", "strong_kp", "medium_kp", "next_focus", "interaction_note"):
                    if args.get(key) is not None:
                        cmd += [f"--{key.replace('_','-')}", str(args.get(key))]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)

            if name == "exam.list":
                return _jsonrpc_ok(req.id, _tool_exam_list())
            if name == "exam.get":
                return _jsonrpc_ok(req.id, _tool_exam_get(args))
            if name == "exam.analysis.get":
                return _jsonrpc_ok(req.id, _tool_exam_analysis_get(args))
            if name == "exam.students.list":
                return _jsonrpc_ok(req.id, _tool_exam_students_list(args))
            if name == "exam.student.get":
                return _jsonrpc_ok(req.id, _tool_exam_student_get(args))
            if name == "exam.question.get":
                return _jsonrpc_ok(req.id, _tool_exam_question_get(args))

            if name == "assignment.list":
                return _jsonrpc_ok(req.id, _tool_assignment_list())
            if name == "lesson.list":
                return _jsonrpc_ok(req.id, _tool_lesson_list())

            if name == "lesson.capture":
                lesson_id = _require_safe_id(args.get("lesson_id"), "lesson_id")
                topic = str(args.get("topic") or "").strip()
                if not topic:
                    raise ValueError("missing required field: topic")
                sources = args.get("sources")
                if not isinstance(sources, list) or not sources:
                    raise ValueError("sources must be a non-empty array of file paths")
                script = APP_ROOT / "skills" / "physics-lesson-capture" / "scripts" / "lesson_capture.py"
                cmd = ["python3", str(script), "--lesson-id", lesson_id, "--topic", topic, "--sources", *[str(s) for s in sources]]
                if args.get("class_name"):
                    cmd += ["--class-name", str(args.get("class_name"))]
                if args.get("discussion_notes"):
                    cmd += ["--discussion-notes", str(args.get("discussion_notes"))]
                if args.get("lesson_plan"):
                    cmd += ["--lesson-plan", str(args.get("lesson_plan"))]
                if args.get("force_ocr"):
                    cmd += ["--force-ocr"]
                if args.get("ocr_mode"):
                    cmd += ["--ocr-mode", str(args.get("ocr_mode"))]
                if args.get("language"):
                    cmd += ["--language", str(args.get("language"))]
                if args.get("out_base"):
                    cmd += ["--out-base", str(args.get("out_base"))]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)

            if name == "core_example.search":
                csv_path = DATA_DIR / "core_examples" / "examples.csv"
                if not csv_path.exists():
                    return _jsonrpc_ok(req.id, [])
                results = []
                with csv_path.open(encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if args.get("kp_id") and row.get("kp_id") != args.get("kp_id"):
                            continue
                        if args.get("example_id") and row.get("example_id") != args.get("example_id"):
                            continue
                        results.append(row)
                return _jsonrpc_ok(req.id, results)

            if name == "core_example.register":
                example_id = _require_safe_id(args.get("example_id"), "example_id")
                kp_id = _require_safe_id(args.get("kp_id"), "kp_id")
                core_model = str(args.get("core_model") or "").strip()
                if not core_model:
                    raise ValueError("missing required field: core_model")
                script = APP_ROOT / "skills" / "physics-core-examples" / "scripts" / "register_core_example.py"
                cmd = ["python3", str(script), "--example-id", example_id, "--kp-id", kp_id, "--core-model", core_model]
                for key in (
                    "difficulty",
                    "source_ref",
                    "tags",
                    "stem_file",
                    "solution_file",
                    "model_file",
                    "figure_file",
                    "discussion_file",
                    "variant_file",
                    "from_lesson",
                    "lesson_example_id",
                    "lesson_figure",
	                ):
	                    if args.get(key):
	                        cmd += [f"--{key.replace('_','-')}", str(args.get(key))]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)

            if name == "core_example.render":
                example_id = _require_safe_id(args.get("example_id"), "example_id")
                script = APP_ROOT / "skills" / "physics-core-examples" / "scripts" / "render_core_example_pdf.py"
                cmd = ["python3", str(script), "--example-id", example_id]
                if args.get("out"):
                    cmd += ["--out", str(args.get("out"))]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)

            if name == "assignment.generate":
                assignment_id = _require_safe_id(args.get("assignment_id"), "assignment_id")
                script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "select_practice.py"
                cmd = ["python3", str(script), "--assignment-id", assignment_id]
                if args.get("kp"):
                    cmd += ["--kp", str(args.get("kp") or "")]
                if args.get("question_ids"):
                    cmd += ["--question-ids", str(args.get("question_ids") or "")]
                if args.get("mode"):
                    cmd += ["--mode", str(args.get("mode"))]
                if args.get("date"):
                    cmd += ["--date", str(args.get("date"))]
                if args.get("class_name"):
                    cmd += ["--class-name", str(args.get("class_name"))]
                if args.get("student_ids"):
                    cmd += ["--student-ids", str(args.get("student_ids"))]
                if args.get("source"):
                    cmd += ["--source", str(args.get("source"))]
                if args.get("per_kp") is not None:
                    cmd += ["--per-kp", str(args.get("per_kp"))]
                if args.get("core_examples"):
                    cmd += ["--core-examples", str(args.get("core_examples"))]
                if args.get("generate"):
                    cmd += ["--generate"]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)

            if name == "assignment.render":
                assignment_id = _require_safe_id(args.get("assignment_id"), "assignment_id")
                script = APP_ROOT / "scripts" / "render_assignment_pdf.py"
                cmd = ["python3", str(script), "--assignment-id", assignment_id]
                if args.get("assignment_questions"):
                    cmd += ["--assignment-questions", str(args.get("assignment_questions"))]
                if args.get("out"):
                    cmd += ["--out", str(args.get("out"))]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)
        except ValueError as exc:
            return _jsonrpc_error(req.id, -32602, str(exc))
        except subprocess.TimeoutExpired as exc:
            return _jsonrpc_error(req.id, -32000, "tool timeout", {"timeout_sec": SCRIPT_TIMEOUT_SEC, "cmd": exc.cmd})
        except HTTPException as exc:
            return _jsonrpc_error(req.id, -32000, str(exc.detail), {"http_status": exc.status_code})
        except Exception as exc:
            _log.debug("operation failed", exc_info=True)
            return _jsonrpc_error(req.id, -32000, f"tool failed: {exc}")

        return _jsonrpc_error(req.id, -32601, f"Unknown tool: {name}")

    return _jsonrpc_error(req.id, -32601, f"Unknown method: {req.method}")
