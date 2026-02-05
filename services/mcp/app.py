from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Union

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", APP_ROOT / "data"))
API_KEY = os.getenv("MCP_API_KEY", "")

app = FastAPI(title="Physics MCP Server", version="0.1.0")


class JsonRpcRequest(BaseModel):
    jsonrpc: str
    id: Optional[Union[str, int]]
    method: str
    params: Dict[str, Any] = {}


TOOLS = [
    {"name": "student.profile.get", "description": "Get student profile"},
    {"name": "student.profile.update", "description": "Update student profile (derived)"},
    {"name": "lesson.capture", "description": "Capture lesson materials (OCR + examples)"},
    {"name": "core_example.search", "description": "Search core examples"},
    {"name": "assignment.generate", "description": "Generate assignment from KP or core examples"},
]


@app.get("/health")
async def health():
    return {"status": "ok"}


def auth(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def run_script(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr or proc.stdout)
    return proc.stdout


@app.post("/mcp")
async def mcp_rpc(req: JsonRpcRequest, x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)

    if req.method == "tools/list":
        return {"jsonrpc": "2.0", "id": req.id, "result": TOOLS}

    if req.method == "tools/call":
        name = req.params.get("name")
        args = req.params.get("arguments", {})
        if name == "student.profile.get":
            student_id = args.get("student_id")
            profile_path = DATA_DIR / "student_profiles" / f"{student_id}.json"
            if not profile_path.exists():
                raise HTTPException(status_code=404, detail="profile not found")
            return {"jsonrpc": "2.0", "id": req.id, "result": json.loads(profile_path.read_text(encoding="utf-8"))}

        if name == "student.profile.update":
            script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
            cmd = ["python3", str(script), "--student-id", args.get("student_id", "")]
            for key in ("weak_kp", "strong_kp", "medium_kp", "next_focus", "interaction_note"):
                if args.get(key) is not None:
                    cmd += [f"--{key.replace('_','-')}", str(args.get(key))]
            out = run_script(cmd)
            return {"jsonrpc": "2.0", "id": req.id, "result": out}

        if name == "lesson.capture":
            script = APP_ROOT / "skills" / "physics-lesson-capture" / "scripts" / "lesson_capture.py"
            cmd = [
                "python3", str(script),
                "--lesson-id", args.get("lesson_id", ""),
                "--topic", args.get("topic", ""),
            ]
            sources = args.get("sources", [])
            if sources:
                cmd += ["--sources", *sources]
            if args.get("discussion_notes"):
                cmd += ["--discussion-notes", args.get("discussion_notes")]
            out = run_script(cmd)
            return {"jsonrpc": "2.0", "id": req.id, "result": out}

        if name == "core_example.search":
            csv_path = DATA_DIR / "core_examples" / "examples.csv"
            if not csv_path.exists():
                return {"jsonrpc": "2.0", "id": req.id, "result": []}
            import csv
            results = []
            with csv_path.open(encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if args.get("kp_id") and row.get("kp_id") != args.get("kp_id"):
                        continue
                    if args.get("example_id") and row.get("example_id") != args.get("example_id"):
                        continue
                    results.append(row)
            return {"jsonrpc": "2.0", "id": req.id, "result": results}

        if name == "assignment.generate":
            script = APP_ROOT / "skills" / "physics-student-coach" / "scripts" / "select_practice.py"
            cmd = ["python3", str(script), "--assignment-id", args.get("assignment_id", "")]
            if args.get("kp"):
                cmd += ["--kp", args.get("kp", "")]
            if args.get("question_ids"):
                cmd += ["--question-ids", args.get("question_ids")]
            if args.get("mode"):
                cmd += ["--mode", args.get("mode")]
            if args.get("date"):
                cmd += ["--date", args.get("date")]
            if args.get("class_name"):
                cmd += ["--class-name", args.get("class_name")]
            if args.get("student_ids"):
                cmd += ["--student-ids", args.get("student_ids")]
            if args.get("source"):
                cmd += ["--source", args.get("source")]
            if args.get("per_kp") is not None:
                cmd += ["--per-kp", str(args.get("per_kp"))]
            if args.get("core_examples"):
                cmd += ["--core-examples", args.get("core_examples")]
            if args.get("generate"):
                cmd += ["--generate"]
            out = run_script(cmd)
            return {"jsonrpc": "2.0", "id": req.id, "result": out}

        raise HTTPException(status_code=400, detail=f"Unknown tool: {name}")

    raise HTTPException(status_code=400, detail=f"Unknown method: {req.method}")
