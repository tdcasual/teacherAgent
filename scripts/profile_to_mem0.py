#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# mem0 config
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mem0_config import get_config, load_dotenv

load_dotenv()


def load_profile(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"profile not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_mem_text(student_id: str, profile: dict, exam_or_assignment: str = "") -> str:
    weak = ", ".join(profile.get("recent_weak_kp", [])) or "(none)"
    strong = ", ".join(profile.get("recent_strong_kp", [])) or "(none)"
    next_focus = profile.get("next_focus", "") or ""
    summary = profile.get("summary", "") or ""
    return (
        "[MEM:STUDENT]\n"
        f"Student: {student_id}\n"
        "Context: 课后练习\n"
        f"Summary: {summary}\n"
        f"Strengths: {strong}\n"
        f"Weaknesses: {weak}\n"
        "Misconceptions: (auto)\n"
        f"Actions: next_focus={next_focus}\n"
        "Sensitive (masked): ScoreBand=? | RankBand=? | Trend=→\n"
        f"FactsRef: {exam_or_assignment or ''}\n"
        "Tags: profile_update"
    )


def main():
    parser = argparse.ArgumentParser(description="Write profile summary to mem0")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--profile", help="path to student profile json")
    parser.add_argument("--ref", help="assignment/exam reference")
    args = parser.parse_args()

    profile_path = Path(args.profile) if args.profile else Path("data/student_profiles") / f"{args.student_id}.json"
    profile = load_profile(profile_path)

    text = build_mem_text(args.student_id, profile, args.ref or "")

    from mem0 import Memory
    from mem0.memory.main import _build_filters_and_metadata

    memory = Memory.from_config(get_config())
    messages = [{"role": "user", "content": text}]
    processed_metadata, effective_filters = _build_filters_and_metadata(user_id=f"student:{args.student_id}")
    result = memory._add_to_vector_store(messages, processed_metadata, effective_filters, infer=False)

    print({"results": result})


if __name__ == "__main__":
    main()
