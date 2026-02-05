#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Use mem0_config for env
ROOT = Path(__file__).resolve().parents[0]
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mem0_config import load_dotenv
from llm_gateway import LLMGateway, UnifiedLLMRequest

load_dotenv()
LLM_GATEWAY = LLMGateway()


def load_summary_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"summary json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_transcript(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"transcript not found: {path}")
    return path.read_text(encoding="utf-8", errors="ignore")


def call_llm_extract(transcript: str) -> dict:
    system = "你是学习诊断信息抽取器，只输出JSON。"
    user = (
        "从以下学生对话中抽取结构化信息，输出JSON对象，字段："
        "student_id(可空), weak_kp(array), strong_kp(array), medium_kp(array), next_focus(string), "
        "interaction_note(string), assignment_id(string, 可空), matched(int可空), graded(int可空), ungraded(int可空)。\n"
        "如果无法确定某字段，留空或空数组。\n"
        f"对话：\n{transcript}\n"
    )
    req = UnifiedLLMRequest(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    result = LLM_GATEWAY.generate(req, allow_fallback=True)
    content = result.text

    try:
        return json.loads(content)
    except Exception:
        # try to extract json block
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            raise ValueError("LLM output not JSON")
        return json.loads(m.group(0))


def list_to_arg(lst):
    if not lst:
        return ""
    return ",".join(lst)


def main():
    parser = argparse.ArgumentParser(description="Finalize a student session: extract summary and update profile")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--transcript", help="path to session transcript (md/txt)")
    parser.add_argument("--summary-json", help="pre-extracted summary json")
    parser.add_argument("--change-threshold", type=int, default=None, help="profile change score threshold")
    parser.add_argument("--accuracy-delta", type=float, default=0.2, help="accuracy delta threshold")
    parser.add_argument("--write-mem0", action="store_true", help="also write mem0 (requires manual confirmation in practice)")
    args = parser.parse_args()

    if not args.transcript and not args.summary_json:
        raise SystemExit("Provide --transcript or --summary-json")

    if args.summary_json:
        summary = load_summary_json(Path(args.summary_json))
    else:
        transcript = load_transcript(Path(args.transcript))
        summary = call_llm_extract(transcript)

    # build update_profile.py call
    updater = PROJECT_ROOT / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
    cmd = [
        sys.executable,
        str(updater),
        "--student-id",
        args.student_id,
        "--weak-kp",
        list_to_arg(summary.get("weak_kp", [])),
        "--strong-kp",
        list_to_arg(summary.get("strong_kp", [])),
        "--medium-kp",
        list_to_arg(summary.get("medium_kp", [])),
        "--next-focus",
        summary.get("next_focus", "") or "",
        "--interaction-note",
        summary.get("interaction_note", "") or "",
    ]

    if summary.get("assignment_id"):
        cmd.extend(["--assignment-id", str(summary.get("assignment_id"))])
    if summary.get("matched") is not None:
        cmd.extend(["--matched", str(summary.get("matched"))])
    if summary.get("graded") is not None:
        cmd.extend(["--graded", str(summary.get("graded"))])
    if summary.get("ungraded") is not None:
        cmd.extend(["--ungraded", str(summary.get("ungraded"))])

    subprocess.run(cmd, check=True)

    # detect profile change and suggest mem0 write
    checker = PROJECT_ROOT / "scripts" / "check_profile_changes.py"
    try:
        threshold = args.change_threshold
        if threshold is None:
            try:
                threshold = int(os.getenv("PROFILE_CHANGE_THRESHOLD", "1"))
            except Exception:
                threshold = 1
        result = subprocess.run(
            [
                sys.executable,
                str(checker),
                "--student-id",
                args.student_id,
                "--threshold",
                str(threshold),
                "--accuracy-delta",
                str(args.accuracy_delta),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        if "CHANGE_DETECTED" in result.stdout:
            print("[INFO] Profile changed; you may want to write mem0 summary.")
    except Exception:
        pass

    # mem0 write is intentionally not automatic unless explicitly requested
    if args.write_mem0:
        print("[WARN] mem0 write requested; please ensure teacher confirmation before executing.")

    print("[OK] Session finalized and profile updated.")


if __name__ == "__main__":
    main()
