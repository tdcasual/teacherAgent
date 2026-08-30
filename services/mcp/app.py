from __future__ import annotations

import csv
import hmac
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

_log = logging.getLogger(__name__)


APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", APP_ROOT / "data"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", APP_ROOT / "uploads"))
API_KEY = os.getenv("MCP_API_KEY", "")
_USER_PATH_ARG_KEYS = frozenset(
    {
        "sources",
        "discussion_notes",
        "lesson_plan",
        "out_base",
        "out",
        "stem_file",
        "solution_file",
        "model_file",
        "figure_file",
        "discussion_file",
        "variant_file",
        "assignment_questions",
    }
)
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

def _docs_enabled() -> bool:
    # Sidecar schema is still scrapeable on loopback; unmount with API docs policy.
    env = (os.getenv("APP_ENV") or os.getenv("ENV") or "development").strip().lower()
    if env in {"prod", "production"}:
        return False
    return str(os.getenv("AUTH_REQUIRED") or "").strip().lower() not in {"1", "true", "yes", "on"}


_docs = _docs_enabled()
app = FastAPI(
    title="MCP Server",
    version="0.2.0",
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

_SAFE_ID_RE = re.compile(r"^[^\x00/\\\\]+$")


class JsonRpcRequest(BaseModel):
    jsonrpc: str
    id: Optional[Union[str, int]]
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)

def _mcp_bound_teacher_id() -> str:
    return str(os.getenv("MCP_BOUND_TEACHER_ID") or "").strip()


def mcp_tool_names() -> List[str]:
    names = [
        "student.search",
        "student.profile.get",
        "lesson.list",
        "core_example.search",
    ]
    if _mcp_bound_teacher_id():
        names.extend(
            [
                "student.profile.update",
                "assignment.list",
                "assignment.render",
                "lesson.capture",
                "core_example.register",
                "core_example.render",
            ]
        )
    return names


MCP_TOOL_NAMES = mcp_tool_names()


def _mcp_tools() -> List[Dict[str, Any]]:
    return [DEFAULT_TOOL_REGISTRY.require(name).to_mcp() for name in mcp_tool_names()]


TOOLS = _mcp_tools()


@app.get("/health")
async def health():
    return {"status": "ok"}


def auth(x_api_key: Optional[str]) -> None:
    expected = (API_KEY or "").encode("utf-8")
    provided = (x_api_key or "").encode("utf-8")
    if not expected:
        raise HTTPException(status_code=503, detail="mcp_auth_not_configured")
    # compare_digest raises on length mismatch; fail closed with 401 instead of 500
    if len(provided) != len(expected) or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _require_contained_path(path_value: Any, field: str) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        raise ValueError(f"missing required field: {field}")
    path = Path(raw)
    if not path.is_absolute():
        path = APP_ROOT / path
    resolved = path.resolve()
    data_root = DATA_DIR.resolve()
    uploads_root = UPLOADS_DIR.resolve()
    if not _is_under_root(resolved, data_root) and not _is_under_root(resolved, uploads_root):
        raise ValueError(f"{field} must be under DATA_DIR or UPLOADS_DIR")
    return str(resolved)


def _require_allowed_script(script_value: Any) -> Path:
    raw = str(script_value or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="script_not_allowed")
    path = Path(raw)
    if not path.is_absolute():
        path = APP_ROOT / path
    resolved = path.resolve()
    allowed_render = (APP_ROOT / "scripts" / "render_assignment_pdf.py").resolve()
    if resolved == allowed_render:
        return resolved
    skills_root = (APP_ROOT / "skills").resolve()
    if not _is_under_root(resolved, skills_root) or resolved.suffix != ".py" or resolved.parent.name != "scripts":
        raise HTTPException(status_code=400, detail="script_not_allowed")
    return resolved


def _optional_contained_arg(args: Dict[str, Any], key: str) -> Optional[str]:
    if not args.get(key):
        return None
    return _require_contained_path(args.get(key), key)


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


def _load_assignment_meta(assignment_id: str) -> Dict[str, Any]:
    meta_path = DATA_DIR / "assignments" / assignment_id / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        _log.debug("JSON parse failed", exc_info=True)
        return {}
    return payload if isinstance(payload, dict) else {}


def _tool_assignment_list() -> Dict[str, Any]:
    bound = _mcp_bound_teacher_id()
    if not bound:
        return {"error": "mcp_teacher_unbound"}
    base = DATA_DIR / "assignments"
    if not base.exists():
        return {"ok": True, "assignments": []}
    items = []
    for folder in base.iterdir():
        if not folder.is_dir():
            continue
        meta = _load_assignment_meta(folder.name)
        if str(meta.get("teacher_id") or "").strip() != bound:
            continue
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
    if len(args) < 2:
        raise HTTPException(status_code=400, detail="script_not_allowed")
    script = _require_allowed_script(args[1])
    cmd = [str(args[0]), str(script), *args[2:]]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(APP_ROOT), timeout=SCRIPT_TIMEOUT_SEC)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr or proc.stdout)
    return proc.stdout


@app.post("/mcp")
async def mcp_rpc(req: JsonRpcRequest, x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)

    if req.method == "tools/list":
        return _jsonrpc_ok(req.id, _mcp_tools())

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
        if name not in mcp_tool_names():
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
                script = APP_ROOT / "skills" / "student-coach" / "scripts" / "update_profile.py"
                cmd = ["python3", str(script), "--student-id", student_id]
                for key in ("weak_kp", "strong_kp", "medium_kp", "next_focus", "interaction_note"):
                    if args.get(key) is not None:
                        cmd += [f"--{key.replace('_','-')}", str(args.get(key))]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)

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
                resolved_sources = [_require_contained_path(s, "sources") for s in sources]
                script = APP_ROOT / "skills" / "physics-lesson-capture" / "scripts" / "lesson_capture.py"
                cmd = ["python3", str(script), "--lesson-id", lesson_id, "--topic", topic, "--sources", *resolved_sources]
                if args.get("class_name"):
                    cmd += ["--class-name", str(args.get("class_name"))]
                discussion_notes = _optional_contained_arg(args, "discussion_notes")
                if discussion_notes:
                    cmd += ["--discussion-notes", discussion_notes]
                lesson_plan = _optional_contained_arg(args, "lesson_plan")
                if lesson_plan:
                    cmd += ["--lesson-plan", lesson_plan]
                if args.get("force_ocr"):
                    cmd += ["--force-ocr"]
                if args.get("ocr_mode"):
                    cmd += ["--ocr-mode", str(args.get("ocr_mode"))]
                if args.get("language"):
                    cmd += ["--language", str(args.get("language"))]
                out_base = _optional_contained_arg(args, "out_base")
                if out_base:
                    cmd += ["--out-base", out_base]
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
                    if not args.get(key):
                        continue
                    value = str(args.get(key))
                    if key in _USER_PATH_ARG_KEYS:
                        value = _require_contained_path(value, key)
                    elif key in {"from_lesson", "lesson_figure"}:
                        value = _require_safe_id(value, key)
                    cmd += [f"--{key.replace('_','-')}", value]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)

            if name == "core_example.render":
                example_id = _require_safe_id(args.get("example_id"), "example_id")
                script = APP_ROOT / "skills" / "physics-core-examples" / "scripts" / "render_core_example_pdf.py"
                cmd = ["python3", str(script), "--example-id", example_id]
                out_path = _optional_contained_arg(args, "out")
                if out_path:
                    cmd += ["--out", out_path]
                out = run_script(cmd)
                return _jsonrpc_ok(req.id, out)

            if name == "assignment.render":
                assignment_id = _require_safe_id(args.get("assignment_id"), "assignment_id")
                bound = _mcp_bound_teacher_id()
                if not bound:
                    return _jsonrpc_error(req.id, 403, "mcp_teacher_unbound")
                meta = _load_assignment_meta(assignment_id)
                owner = str(meta.get("teacher_id") or "").strip()
                if not meta:
                    return _jsonrpc_error(req.id, 404, "assignment not found", {"assignment_id": assignment_id})
                if owner != bound:
                    return _jsonrpc_error(req.id, 403, "forbidden_assignment_owner", {"assignment_id": assignment_id})
                script = APP_ROOT / "scripts" / "render_assignment_pdf.py"
                cmd = ["python3", str(script), "--assignment-id", assignment_id]
                assignment_questions = _optional_contained_arg(args, "assignment_questions")
                if assignment_questions:
                    cmd += ["--assignment-questions", assignment_questions]
                out_path = _optional_contained_arg(args, "out")
                if out_path:
                    cmd += ["--out", out_path]
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
