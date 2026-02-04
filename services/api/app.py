from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", APP_ROOT / "data"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", APP_ROOT / "uploads"))

app = FastAPI(title="Physics Agent API", version="0.1.0")

origins = os.getenv("CORS_ORIGINS", "*")
origins_list = [o.strip() for o in origins.split(",")] if origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_script(args: list[str]):
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr or proc.stdout)
    return proc.stdout


@app.get("/health")
async def health():
    return {"status": "ok"}


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
