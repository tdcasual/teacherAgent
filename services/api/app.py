from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from mem0_config import load_dotenv

    load_dotenv()
except Exception:
    pass

APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", APP_ROOT / "data"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", APP_ROOT / "uploads"))

app = FastAPI(title="Physics Agent API", version="0.2.0")

origins = os.getenv("CORS_ORIGINS", "*")
origins_list = [o.strip() for o in origins.split(",")] if origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    role: Optional[str] = None


class StudentImportRequest(BaseModel):
    source: Optional[str] = None
    exam_id: Optional[str] = None
    file_path: Optional[str] = None
    mode: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    role: Optional[str] = None


def run_script(args: List[str]) -> str:
    env = os.environ.copy()
    root = str(APP_ROOT)
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{root}{os.pathsep}{current}" if current else root
    proc = subprocess.run(args, capture_output=True, text=True, env=env, cwd=root)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr or proc.stdout)
    return proc.stdout


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def detect_role(text: str) -> Optional[str]:
    normalized = normalize(text)
    if "老师" in normalized or "教师" in normalized:
        return "teacher"
    if "学生" in normalized:
        return "student"
    return None


def load_profile_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def student_search(query: str, limit: int = 5) -> Dict[str, Any]:
    profiles_dir = DATA_DIR / "student_profiles"
    if not profiles_dir.exists():
        return {"matches": []}

    q_norm = normalize(query)
    matches = []
    for path in profiles_dir.glob("*.json"):
        profile = load_profile_file(path)
        student_id = profile.get("student_id") or path.stem
        candidates = [
            student_id,
            profile.get("student_name", ""),
            profile.get("class_name", ""),
        ] + (profile.get("aliases") or [])

        best_score = 0.0
        for cand in candidates:
            if not cand:
                continue
            cand_norm = normalize(str(cand))
            if not cand_norm:
                continue
            if q_norm and q_norm in cand_norm:
                score = 1.0
            else:
                score = SequenceMatcher(None, q_norm, cand_norm).ratio() if q_norm else 0.0
            if score > best_score:
                best_score = score

        if best_score > 0.1:
            matches.append(
                {
                    "student_id": student_id,
                    "student_name": profile.get("student_name", ""),
                    "class_name": profile.get("class_name", ""),
                    "score": round(best_score, 3),
                }
            )

    matches.sort(key=lambda x: x["score"], reverse=True)
    return {"matches": matches[:limit]}


def student_profile_get(student_id: str) -> Dict[str, Any]:
    profile_path = DATA_DIR / "student_profiles" / f"{student_id}.json"
    if not profile_path.exists():
        return {"error": "profile not found", "student_id": student_id}
    return json.loads(profile_path.read_text(encoding="utf-8"))


def student_profile_update(args: Dict[str, Any]) -> Dict[str, Any]:
    script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
    cmd = ["python3", str(script), "--student-id", args.get("student_id", "")]
    for key in ("weak_kp", "strong_kp", "medium_kp", "next_focus", "interaction_note"):
        if args.get(key) is not None:
            cmd += [f"--{key.replace('_', '-')}", str(args.get(key))]
    out = run_script(cmd)
    return {"ok": True, "output": out}


def count_csv_rows(path: Path) -> int:
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            count = -1
            for count, _ in enumerate(reader):
                pass
        return max(count, 0)
    except Exception:
        return 0


def list_exams() -> Dict[str, Any]:
    exams_dir = DATA_DIR / "exams"
    if not exams_dir.exists():
        return {"exams": []}

    items = []
    for folder in exams_dir.iterdir():
        if not folder.is_dir():
            continue
        manifest_path = folder / "manifest.json"
        data = load_profile_file(manifest_path) if manifest_path.exists() else {}
        exam_id = data.get("exam_id") or folder.name
        generated_at = data.get("generated_at")
        counts = data.get("counts", {})
        items.append(
            {
                "exam_id": exam_id,
                "generated_at": generated_at,
                "students": counts.get("students"),
                "responses": counts.get("responses"),
            }
        )

    items.sort(key=lambda x: x.get("generated_at") or "", reverse=True)
    return {"exams": items}


def list_assignments() -> Dict[str, Any]:
    assignments_dir = DATA_DIR / "assignments"
    if not assignments_dir.exists():
        return {"assignments": []}

    items = []
    for folder in assignments_dir.iterdir():
        if not folder.is_dir():
            continue
        assignment_id = folder.name
        questions_path = folder / "questions.csv"
        count = count_csv_rows(questions_path) if questions_path.exists() else 0
        updated_at = None
        if questions_path.exists():
            updated_at = datetime.fromtimestamp(questions_path.stat().st_mtime).isoformat(timespec="seconds")
        items.append(
            {
                "assignment_id": assignment_id,
                "question_count": count,
                "updated_at": updated_at,
            }
        )

    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"assignments": items}


def list_lessons() -> Dict[str, Any]:
    lessons_dir = DATA_DIR / "lessons"
    if not lessons_dir.exists():
        return {"lessons": []}

    items = []
    for folder in lessons_dir.iterdir():
        if not folder.is_dir():
            continue
        lesson_id = folder.name
        summary = ""
        meta_path = folder / "lesson.json"
        if meta_path.exists():
            meta = load_profile_file(meta_path)
            lesson_id = meta.get("lesson_id") or lesson_id
            summary = meta.get("summary", "")
        items.append({"lesson_id": lesson_id, "summary": summary})

    items.sort(key=lambda x: x.get("lesson_id") or "")
    return {"lessons": items}


def list_skills() -> Dict[str, Any]:
    skills_dir = APP_ROOT / "skills"
    if not skills_dir.exists():
        return {"skills": []}

    items = []
    for folder in sorted(skills_dir.iterdir(), key=lambda p: p.name):
        if not folder.is_dir():
            continue
        skill_id = folder.name
        title = skill_id
        desc = ""
        skill_file = folder / "SKILL.md"
        if skill_file.exists():
            lines = skill_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            if lines and lines[0].strip() == "---":
                end_idx = None
                for idx in range(1, len(lines)):
                    if lines[idx].strip() == "---":
                        end_idx = idx
                        break
                if end_idx:
                    front = lines[1:end_idx]
                    for line in front:
                        if ":" not in line:
                            continue
                        key, val = line.split(":", 1)
                        key = key.strip().lower()
                        val = val.strip()
                        if key == "description" and val:
                            desc = val
                        if key == "title" and val:
                            title = val
                        if key == "name" and not title:
                            title = val
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("# "):
                    title = stripped[2:].strip()
                    continue
                if stripped and not stripped.startswith("#") and not desc and stripped != "---":
                    desc = stripped
        items.append({"id": skill_id, "title": title, "desc": desc})

    return {"skills": items}


def resolve_responses_file(exam_id: Optional[str], file_path: Optional[str]) -> Optional[Path]:
    if file_path:
        path = Path(file_path)
        if not path.is_absolute():
            path = APP_ROOT / path
        return path if path.exists() else None

    if exam_id:
        manifest_path = DATA_DIR / "exams" / exam_id / "manifest.json"
        if manifest_path.exists():
            manifest = load_profile_file(manifest_path)
            files = manifest.get("files", {})
            resp_path = files.get("responses")
            if resp_path:
                candidate = Path(resp_path)
                if not candidate.is_absolute():
                    if str(resp_path).startswith("data/"):
                        candidate = APP_ROOT / candidate
                    else:
                        candidate = DATA_DIR / candidate
                return candidate if candidate.exists() else None

    staging_dir = DATA_DIR / "staging"
    if staging_dir.exists():
        candidates = list(staging_dir.glob("*responses*scored*.csv"))
        if not candidates:
            candidates = list(staging_dir.glob("*responses*.csv"))
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]
    return None


def import_students_from_responses(path: Path, mode: str = "merge") -> Dict[str, Any]:
    if not path.exists():
        return {"error": f"responses file not found: {path}"}

    profiles_dir = DATA_DIR / "student_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    students: Dict[str, Dict[str, str]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            student_id = (row.get("student_id") or "").strip()
            student_name = (row.get("student_name") or "").strip()
            class_name = (row.get("class_name") or "").strip()
            exam_id = (row.get("exam_id") or "").strip()
            if not student_id:
                if class_name and student_name:
                    student_id = f"{class_name}_{student_name}"
                elif student_name:
                    student_id = student_name
            if not student_id:
                continue
            if student_id not in students:
                students[student_id] = {
                    "student_id": student_id,
                    "student_name": student_name,
                    "class_name": class_name,
                    "exam_id": exam_id,
                }

    created = 0
    updated = 0
    skipped = 0
    sample = []

    for student_id, info in students.items():
        profile_path = profiles_dir / f"{student_id}.json"
        profile = load_profile_file(profile_path) if profile_path.exists() else {}
        is_new = not bool(profile)

        if is_new:
            created += 1
        else:
            updated += 1

        profile.setdefault("student_id", student_id)
        profile.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        profile["last_updated"] = datetime.now().isoformat(timespec="seconds")

        if info.get("student_name"):
            if not profile.get("student_name"):
                profile["student_name"] = info["student_name"]
            elif profile.get("student_name") != info["student_name"]:
                aliases = set(profile.get("aliases", []))
                aliases.add(info["student_name"])
                profile["aliases"] = sorted(aliases)

        if info.get("class_name") and not profile.get("class_name"):
            profile["class_name"] = info["class_name"]

        history = profile.get("import_history", [])
        history.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "source": "exam_responses",
                "file": str(path),
                "exam_id": info.get("exam_id") or "",
                "mode": mode,
            }
        )
        profile["import_history"] = history[-10:]

        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        if len(sample) < 10:
            sample.append(student_id)

    total = len(students)
    if total == 0:
        skipped = 0
    return {
        "ok": True,
        "source_file": str(path),
        "total_students": total,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "sample": sample,
    }


def student_import(args: Dict[str, Any]) -> Dict[str, Any]:
    source = args.get("source") or "responses_scored"
    exam_id = args.get("exam_id")
    file_path = args.get("file_path")
    mode = args.get("mode") or "merge"
    if source not in {"responses_scored", "responses"}:
        return {"error": f"unsupported source: {source}"}
    responses_path = resolve_responses_file(exam_id, file_path)
    if not responses_path:
        return {"error": "responses file not found", "exam_id": exam_id, "file_path": file_path}
    return import_students_from_responses(responses_path, mode=mode)


def assignment_generate(args: Dict[str, Any]) -> Dict[str, Any]:
    script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "select_practice.py"
    cmd = [
        "python3",
        str(script),
        "--assignment-id",
        str(args.get("assignment_id", "")),
        "--kp",
        str(args.get("kp", "")),
    ]
    per_kp = args.get("per_kp")
    if per_kp is not None:
        cmd += ["--per-kp", str(per_kp)]
    if args.get("core_examples"):
        cmd += ["--core-examples", str(args.get("core_examples"))]
    if args.get("generate"):
        cmd += ["--generate"]
    out = run_script(cmd)
    return {"ok": True, "output": out, "assignment_id": args.get("assignment_id")}


def assignment_render(args: Dict[str, Any]) -> Dict[str, Any]:
    script = APP_ROOT / "scripts" / "render_assignment_pdf.py"
    assignment_id = str(args.get("assignment_id", ""))
    out = run_script(["python3", str(script), "--assignment-id", assignment_id])
    return {"ok": True, "output": out, "pdf": f"output/pdf/assignment_{assignment_id}.pdf"}


def tool_dispatch(name: str, args: Dict[str, Any], role: Optional[str] = None) -> Dict[str, Any]:
    if name == "exam.list":
        return list_exams()
    if name == "assignment.list":
        return list_assignments()
    if name == "lesson.list":
        return list_lessons()
    if name == "student.search":
        return student_search(args.get("query", ""), int(args.get("limit", 5)))
    if name == "student.profile.get":
        return student_profile_get(args.get("student_id", ""))
    if name == "student.profile.update":
        return student_profile_update(args)
    if name == "student.import":
        if role != "teacher":
            return {"error": "permission denied", "detail": "student.import requires teacher role"}
        return student_import(args)
    if name == "assignment.generate":
        return assignment_generate(args)
    if name == "assignment.render":
        return assignment_render(args)
    return {"error": f"unknown tool: {name}"}


def get_llm_config() -> Dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OPENAI_API_KEY or SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("SILICONFLOW_LLM_MODEL", "deepseek-ai/DeepSeek-V3.2")
    return {"api_key": api_key, "base_url": base_url, "model": model}


def call_llm(messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    cfg = get_llm_config()
    payload: Dict[str, Any] = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    resp = requests.post(
        cfg["base_url"].rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def parse_tool_json(content: str) -> Optional[Dict[str, Any]]:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n|```$", "", text, flags=re.S).strip()
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except Exception:
            return None
    if isinstance(data, dict) and data.get("tool"):
        return data
    return None


def build_system_prompt(role_hint: Optional[str]) -> str:
    role_text = role_hint if role_hint else "unknown"
    if role_text == "student":
        return (
            "你是学生端的物理学习助手，只回答学科问题与学习指导。\n"
            "不要调用任何管理类工具，也不要生成或修改学生档案。\n"
            "如果用户提出老师端功能（如导入名册、生成作业、列出考试等），请说明学生端不支持。\n"
        )
    if role_text == "teacher":
        return (
            "你是物理教学助手，必须通过工具获取学生画像、作业信息，不可编造事实。\n"
            "当前身份提示：teacher。\n"
            "若用户只提供姓名或昵称，先调用 student.search 获得候选列表，再请用户确认 student_id。\n"
            "当老师要求导入学生名册或初始化学生档案时，调用 student.import。\n"
            "当老师要求列出考试、作业或课程时，分别调用 exam.list、assignment.list、lesson.list。\n"
            "工具调用优先，其它内容仅在工具返回后总结输出。\n"
            "如果无法使用函数调用，请仅输出单行JSON，如：{\"tool\":\"student.search\",\"arguments\":{\"query\":\"武熙语\"}}。\n"
        )
    return (
        "你是物理教学助手，必须通过工具获取学生画像、作业信息，不可编造事实。\n"
        f"当前身份提示：{role_text}。请先要求对方确认是老师还是学生。\n"
    )


def allowed_tools(role_hint: Optional[str]) -> set:
    if role_hint == "teacher":
        return {
            "exam.list",
            "assignment.list",
            "lesson.list",
            "student.search",
            "student.profile.get",
            "student.profile.update",
            "student.import",
            "assignment.generate",
            "assignment.render",
        }
    return set()


def run_agent(messages: List[Dict[str, Any]], role_hint: Optional[str]) -> Dict[str, Any]:
    system_message = {"role": "system", "content": build_system_prompt(role_hint)}
    convo = [system_message] + messages

    teacher_tools = [
        {
            "type": "function",
            "function": {
                "name": "exam.list",
                "description": "List available exams and exam ids",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "assignment.list",
                "description": "List available assignments",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lesson.list",
                "description": "List available lessons",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "student.search",
                "description": "Search student ids by name or keyword",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "name or keyword"},
                        "limit": {"type": "integer", "description": "max results", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "student.profile.get",
                "description": "Get student profile by student_id",
                "parameters": {
                    "type": "object",
                    "properties": {"student_id": {"type": "string"}},
                    "required": ["student_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "student.profile.update",
                "description": "Update derived fields in student profile",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "student_id": {"type": "string"},
                        "weak_kp": {"type": "string"},
                        "medium_kp": {"type": "string"},
                        "strong_kp": {"type": "string"},
                        "next_focus": {"type": "string"},
                        "interaction_note": {"type": "string"},
                    },
                    "required": ["student_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "student.import",
                "description": "Import students from exam responses into student_profiles",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "responses_scored or responses",
                            "default": "responses_scored",
                        },
                        "exam_id": {"type": "string", "description": "exam id to locate manifest"},
                        "file_path": {"type": "string", "description": "override responses csv path"},
                        "mode": {"type": "string", "description": "merge or overwrite", "default": "merge"},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "assignment.generate",
                "description": "Generate assignment from KP",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "assignment_id": {"type": "string"},
                        "kp": {"type": "string"},
                        "per_kp": {"type": "integer"},
                        "core_examples": {"type": "string"},
                        "generate": {"type": "boolean"},
                    },
                    "required": ["assignment_id", "kp"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "assignment.render",
                "description": "Render assignment PDF",
                "parameters": {
                    "type": "object",
                    "properties": {"assignment_id": {"type": "string"}},
                    "required": ["assignment_id"],
                },
            },
        },
    ]
    allowed = allowed_tools(role_hint)
    tools = teacher_tools if role_hint == "teacher" else []

    for _ in range(3):
        resp = call_llm(convo, tools=tools)
        message = resp["choices"][0]["message"]
        content = message.get("content")
        tool_calls = message.get("tool_calls")
        if tool_calls:
            convo.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
            for call in tool_calls:
                name = call["function"]["name"]
                if name not in allowed:
                    result = {"error": "permission denied", "tool": name}
                    convo.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                    continue
                args = call["function"].get("arguments") or "{}"
                try:
                    args_dict = json.loads(args)
                except Exception:
                    args_dict = {}
                result = tool_dispatch(name, args_dict, role=role_hint)
                convo.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            continue

        tool_request = parse_tool_json(content or "")
        if tool_request:
            name = tool_request.get("tool")
            if name not in allowed:
                convo.append({"role": "assistant", "content": content or ""})
                convo.append(
                    {
                        "role": "user",
                        "content": f"工具 {name} 无权限调用。请给出最终答复。",
                    }
                )
                continue
            args_dict = tool_request.get("arguments") or {}
            result = tool_dispatch(name, args_dict, role=role_hint)
            convo.append({"role": "assistant", "content": content or ""})
            convo.append(
                {
                    "role": "user",
                    "content": f"工具 {name} 返回: {json.dumps(result, ensure_ascii=False)}。请给出最终答复。",
                }
            )
            continue

        return {"reply": content or ""}

    return {"reply": "工具调用过多，请明确你的需求或缩小范围。"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    role_hint = req.role
    if not role_hint or role_hint == "unknown":
        for msg in reversed(req.messages):
            if msg.role == "user":
                detected = detect_role(msg.content)
                if detected:
                    role_hint = detected
                    break
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    result = run_agent(messages, role_hint)
    return ChatResponse(reply=result["reply"], role=role_hint)


@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        dest = UPLOADS_DIR / f.filename
        content = await f.read()
        dest.write_bytes(content)
        saved.append(str(dest))
    return {"saved": saved}


@app.get("/student/profile/{student_id}")
async def get_profile(student_id: str):
    profile_path = DATA_DIR / "student_profiles" / f"{student_id}.json"
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="profile not found")
    return json.loads(profile_path.read_text(encoding="utf-8"))


@app.post("/student/profile/update")
async def update_profile(
    student_id: str = Form(...),
    weak_kp: Optional[str] = Form(""),
    strong_kp: Optional[str] = Form(""),
    medium_kp: Optional[str] = Form(""),
    next_focus: Optional[str] = Form(""),
    interaction_note: Optional[str] = Form(""),
):
    script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
    args = [
        "python3",
        str(script),
        "--student-id",
        student_id,
        "--weak-kp",
        weak_kp or "",
        "--strong-kp",
        strong_kp or "",
        "--medium-kp",
        medium_kp or "",
        "--next-focus",
        next_focus or "",
        "--interaction-note",
        interaction_note or "",
    ]
    out = run_script(args)
    return JSONResponse({"ok": True, "output": out})


@app.post("/student/import")
async def import_students(req: StudentImportRequest):
    result = student_import(req.dict())
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/exams")
async def exams():
    return list_exams()


@app.get("/assignments")
async def assignments():
    return list_assignments()


@app.get("/lessons")
async def lessons():
    return list_lessons()


@app.get("/skills")
async def skills():
    return list_skills()


@app.post("/assignment/generate")
async def generate_assignment(
    assignment_id: str = Form(...),
    kp: str = Form(...),
    per_kp: int = Form(5),
    core_examples: Optional[str] = Form(""),
    generate: bool = Form(False),
):
    script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "select_practice.py"
    args = [
        "python3",
        str(script),
        "--assignment-id",
        assignment_id,
        "--kp",
        kp,
        "--per-kp",
        str(per_kp),
    ]
    if core_examples:
        args += ["--core-examples", core_examples]
    if generate:
        args += ["--generate"]
    out = run_script(args)
    return {"ok": True, "output": out}


@app.post("/assignment/render")
async def render_assignment(assignment_id: str = Form(...)):
    script = APP_ROOT / "scripts" / "render_assignment_pdf.py"
    out = run_script(["python3", str(script), "--assignment-id", assignment_id])
    return {"ok": True, "output": out}


@app.post("/student/submit")
async def submit(
    student_id: str = Form(...),
    files: list[UploadFile] = File(...),
    assignment_id: Optional[str] = Form(None),
    auto_assignment: bool = Form(False),
):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_paths = []
    for f in files:
        dest = UPLOADS_DIR / f.filename
        dest.write_bytes(await f.read())
        file_paths.append(str(dest))

    script = APP_ROOT / "scripts" / "grade_submission.py"
    args = ["python3", str(script), "--student-id", student_id, "--files", *file_paths]
    if assignment_id:
        args += ["--assignment-id", assignment_id]
    if auto_assignment or not assignment_id:
        args += ["--auto-assignment"]
    out = run_script(args)
    return {"ok": True, "output": out}
